"""API-Football provider support for :class:`SoccerLiveSensor`.

This mixin groups the API-Football URL building, fetching (with per-endpoint
caching, auth-failure and rate-limit handling), and match/club/prematch
enrichment helpers. Split out of ``sensor.py`` to keep that module smaller.

Process-wide state (endpoint cache, back-off timers, call stats) stays declared
as class attributes on ``SoccerLiveSensor``; the methods here reach it through
``cls`` / ``type(self)``, which resolve to that class via the MRO.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from time import monotonic
from urllib.parse import urlencode

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PROVIDER_API_FOOTBALL
from .polling import request_priority_plan

_LOGGER = logging.getLogger(__name__)


class ApiFootballMixin:
    def _build_api_football_url(self):
        if not self._api_football_key:
            self._last_error = "API-Football key is missing"
            return None

        season = self._api_football_effective_season()
        start, end = self._api_football_date_range()
        params = {}

        if self._sensor_type in {"team_match", "team_matches", "team_matches_mixed"}:
            if not self._team_id:
                self._last_error = "API-Football team_id is missing"
                return None
            params = {"team": self._team_id, "season": season}
            if start and end:
                params.update({"from": start, "to": end})
            return f"{self.api_football_base_url}/fixtures?{urlencode(params)}"

        if self._sensor_type == "all_matches_today":
            return f"{self.api_football_base_url}/fixtures?{urlencode({'date': self._local_today_str()})}"

        if self._sensor_type == "match_day" and self._code:
            params = {"league": self._code, "season": season}
            if start and end:
                params.update({"from": start, "to": end})
            return f"{self.api_football_base_url}/fixtures?{urlencode(params)}"

        if self._sensor_type == "standings" and self._code:
            return f"{self.api_football_base_url}/standings?{urlencode({'league': self._code, 'season': season})}"

        if self._sensor_type == "top_scorers" and self._code:
            return f"{self.api_football_base_url}/players/topscorers?{urlencode({'league': self._code, 'season': season})}"

        if self._sensor_type == "bracket" and self._code:
            return f"{self.api_football_base_url}/fixtures?{urlencode({'league': self._code, 'season': season})}"

        self._last_error = f"{self._sensor_type} is not supported by API-Football provider yet"
        return None

    def _api_football_effective_season(self):
        if self._api_football_season:
            return self._api_football_season
        start = self._dyn_start_date or self._start_date
        end = self._dyn_end_date or self._end_date
        now = datetime.now()
        if self._sensor_type in {"standings", "top_scorers"} and now.month < 8:
            return now.year - 1
        if start and end:
            if start.year == end.year:
                return start.year
            if start <= now <= end:
                return now.year
            return start.year
        if start:
            return start.year
        return now.year

    def _api_football_date_range(self):
        start = self._dyn_start_date or self._start_date
        end = self._dyn_end_date or self._end_date
        if start and end:
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        return "", ""

    async def _enrich_with_api_football_fixture(self):
        matches = self._attributes.get("matches") or []
        if not matches:
            return

        plan = request_priority_plan(
            matches, quota=getattr(self, "_api_football_quota", {})
        )
        self._attributes["request_priority_plan"] = plan
        allowed = set(plan["allowed"])

        # H2H is the most useful enrichment for an upcoming fixture and costs a
        # single, 24-hour cached request. Fetch it before enriching historical
        # fixtures: a list sensor can otherwise spend up to fifteen requests on
        # events/statistics/lineups and enter provider backoff before H2H runs.
        if "head_to_head" in allowed:
            await self._enrich_api_football_head_to_head(matches)

        if self._sensor_type in {"team_matches", "team_matches_mixed"}:
            targets = self._api_football_team_list_enrichment_targets(matches)
        else:
            # Single-match card: don't burn quota enriching a match that is still
            # far off — events/statistics/lineups only exist close to kickoff.
            now = datetime.now(timezone.utc)
            targets = [m for m in matches if self._should_enrich_api_football_target(m, now)]

        from .parsers.api_football import process_fixture_enrichment
        for match in targets:
            event_id = match.get("event_id")
            if not event_id:
                continue

            if event_id in self._summary_cache:
                match.update(self._summary_cache[event_id])
                continue

            events_data, statistics_data, lineups_data = await asyncio.gather(
                self._fetch_api_football_json("fixtures/events", {"fixture": event_id})
                if "timeline" in allowed else asyncio.sleep(0, result=None),
                self._fetch_api_football_json("fixtures/statistics", {"fixture": event_id})
                if "statistics" in allowed else asyncio.sleep(0, result=None),
                self._fetch_api_football_json("fixtures/lineups", {"fixture": event_id})
                if "lineup" in allowed else asyncio.sleep(0, result=None),
            )
            if not any(self._api_football_response_has_items(d) for d in (events_data, statistics_data, lineups_data)):
                continue

            enrichment = await self.hass.async_add_executor_job(
                process_fixture_enrichment,
                events_data,
                statistics_data,
                lineups_data,
                match.get("home_id"),
                match.get("away_id"),
            )
            match.update(enrichment)
            if match.get("state") == "post":
                if len(self._summary_cache) >= 20:
                    self._summary_cache.pop(next(iter(self._summary_cache)))
                self._summary_cache[event_id] = enrichment

        if "prematch" in allowed:
            await self._enrich_api_football_prematch(matches)

        self._detect_and_dispatch_goals(matches, self._pending_events)
        self._detect_and_dispatch_cards(matches, self._pending_events)
        self._detect_and_dispatch_match_finished(matches, self._pending_events)
        self._detect_and_dispatch_match_started(matches, self._pending_events)
        self._refresh_api_football_enriched_schedule_attributes(matches)

    async def _enrich_api_football_head_to_head(self, matches):
        """Attach recent completed meetings to relevant selectable fixtures.

        Team IDs are sorted in the request so every sensor following the same
        matchup shares one 24-hour endpoint-cache entry. Single-match sensors
        only need their active fixture; list sensors enrich the first three
        live/upcoming fixtures so changing the card selector keeps H2H useful
        without fetching the entire season.
        """
        from .parsers.api_football import process_head_to_head_data

        for target in self._api_football_h2h_targets(matches):
            if target.get("head_to_head"):
                continue
            try:
                team_ids = sorted(
                    (int(target.get("home_id")), int(target.get("away_id")))
                )
            except (TypeError, ValueError):
                continue
            if team_ids[0] <= 0 or team_ids[0] == team_ids[1]:
                continue

            data = await self._fetch_api_football_json(
                "fixtures/headtohead",
                {"h2h": f"{team_ids[0]}-{team_ids[1]}", "last": 8},
            )
            if not self._api_football_response_has_items(data):
                continue

            head_to_head = await self.hass.async_add_executor_job(
                process_head_to_head_data, data, self.hass, 8
            )
            if head_to_head:
                target["head_to_head"] = head_to_head

    def _api_football_h2h_targets(self, matches):
        """Return the active fixtures whose H2H can be selected in the card."""
        if self._sensor_type not in {"team_matches", "team_matches_mixed"}:
            target = self._prematch_target_match(matches)
            return [target] if target else []

        live = [m for m in matches if m.get("state") == "in" and m.get("event_id")]
        upcoming = [
            m for m in matches if m.get("state") == "pre" and m.get("event_id")
        ]
        upcoming.sort(key=lambda m: m.get("date_iso") or "")
        return (live + upcoming)[:3]

    def _next_upcoming_api_football_match(self, matches):
        """The nearest not-yet-started match with an event id, or None."""
        upcoming = [m for m in matches if m.get("state") == "pre" and m.get("event_id")]
        if not upcoming:
            return None
        upcoming.sort(key=lambda m: m.get("date_iso") or "")
        return upcoming[0]

    async def _enrich_api_football_prematch(self, matches):
        """Attach pre-match prediction/odds/injuries/standing to the next match,
        cache the snapshot by fixture id, and re-attach it to a match that is now
        live/finished so the pre-match context stays visible without new requests."""
        match = self._prematch_target_match(matches)
        if match:
            await self._fetch_and_store_prematch(match)
        self._reattach_prematch(matches)

    async def _enrich_api_football_assists(self):
        """Attach a real top-assists ranking (API-Football /players/topassists) to
        a top_scorers sensor, so the Scorers card's assists mode is the actual
        competition-wide assist leaders, not just assists among the top scorers."""
        if self._provider != PROVIDER_API_FOOTBALL or self._sensor_type != "top_scorers" or not self._code:
            return
        season = self._api_football_effective_season()
        data = await self._fetch_api_football_json(
            "players/topassists", {"league": self._code, "season": season}
        )
        if data is None:
            return
        from .parsers.api_football import process_scorers_data
        parsed = await self.hass.async_add_executor_job(process_scorers_data, data)
        assists = (parsed or {}).get("scorers") or []
        if assists:
            self._attributes["assists"] = assists

    def _api_football_response_has_items(self, data):
        if not isinstance(data, dict):
            return False
        response = data.get("response")
        return isinstance(response, list) and bool(response)

    def _api_football_team_list_enrichment_targets(self, matches):
        now = datetime.now(timezone.utc)
        live = [m for m in matches if m.get("state") == "in"]
        recent_finished = [
            m for m in matches
            if self._should_enrich_recent_finished_api_football_match(m, now)
        ]
        latest_finished = [m for m in matches if m.get("state") == "post"][-5:]
        targets = []
        seen = set()
        for match in live + recent_finished + latest_finished:
            event_id = match.get("event_id")
            key = event_id or f"{match.get('date_iso')}|{match.get('home_team')}|{match.get('away_team')}"
            if key in seen:
                continue
            seen.add(key)
            targets.append(match)
        return targets

    def _refresh_api_football_enriched_schedule_attributes(self, matches):
        if self._sensor_type not in {"team_matches", "team_matches_mixed", "all_matches_today", "match_day"}:
            return
        self._attributes.update(self._compute_all_matches_attributes(matches, [], detect_events=False))
        current_next = self._attributes.get("next_match")
        if isinstance(current_next, dict):
            current_id = current_next.get("event_id")
            refreshed_next = next((m for m in matches if m.get("event_id") == current_id), None)
            if refreshed_next:
                self._attributes["next_match"] = refreshed_next

    def _should_enrich_api_football_target(self, match, now):
        """Whether a single-match card should fetch enrichment for this match.

        Live and finished matches are always enriched. An upcoming match is only
        enriched once kickoff is within reach (lineups appear ~1h before, stats
        and events only during play), so a match days away doesn't repeatedly
        fetch three empty endpoints and waste the API quota."""
        if match.get("state") != "pre":
            return True
        raw_date = match.get("date_iso")
        if not raw_date:
            return False
        try:
            kickoff = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
            if kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=timezone.utc)
            kickoff = kickoff.astimezone(timezone.utc)
        except ValueError:
            return False
        return (kickoff - now) <= timedelta(hours=3)

    def _should_enrich_recent_finished_api_football_match(self, match, now):
        if match.get("state") != "post":
            return False
        if match.get("match_details") or match.get("key_events"):
            return False
        raw_date = match.get("date_iso")
        if not raw_date:
            return False
        try:
            match_date = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
            if match_date.tzinfo is None:
                match_date = match_date.replace(tzinfo=timezone.utc)
            match_date = match_date.astimezone(timezone.utc)
        except ValueError:
            return False
        recent_hours = max(int(self._recent_match_hours or 0), 1)
        return match_date <= now and now - match_date <= timedelta(hours=recent_hours)

    @classmethod
    def _af_stat(cls, path):
        return cls._api_football_stats.setdefault(
            path, {"calls": 0, "cache_hits": 0, "last_success": None, "last_status": None}
        )

    @classmethod
    def _af_enrichment_paused(cls):
        pause = cls._af_enrich_pause_until
        return pause is not None and monotonic() < pause

    @staticmethod
    def _af_is_rate_limit_message(msg):
        """Whether an API-Football 200-body error message is a rate/quota limit
        (per-minute or per-day), so it can be handled like an HTTP 429."""
        m = (msg or "").lower()
        return (
            "too many requests" in m
            or "requests per minute" in m
            or "requests per day" in m
            or "request limit" in m
            or "rate limit" in m
            or "ratelimit" in m
        )

    @staticmethod
    def _af_is_daily_limit_message(msg):
        """A per-day quota exhaustion (vs a transient per-minute burst). Retrying
        every 30 min all day is pointless, so these pause until the next reset."""
        m = (msg or "").lower()
        return "per day" in m or "for the day" in m or "daily" in m

    def _af_handle_rate_limit(self, path, reason):
        """Pause enrichment on a rate/quota limit. Only the first hit (while not
        already paused) starts the pause and logs — at INFO, since it's an
        expected, self-healing condition (e.g. the burst after a restart) and the
        last cached data keeps being served. Concurrent stragglers from the same
        burst are dropped to DEBUG so they don't spam the log or balloon the
        backoff. A per-day quota pauses until the next reset; a per-minute limit
        uses the doubling backoff. Diagnostics expose the pause (rate_limited_at)."""
        if self._af_enrichment_paused():
            _LOGGER.debug("API-Football still rate-limited while fetching %s (%s)", path, reason)
            return
        if self._af_is_daily_limit_message(reason):
            pause_seconds = self._af_note_daily_limit()
            _LOGGER.info(
                "API-Football daily quota reached while fetching %s (%s) — pausing enrichment "
                "for %.0f s until the next quota reset; serving cached data meanwhile",
                path, reason, pause_seconds,
            )
        else:
            self._af_note_rate_limited()
            _LOGGER.info(
                "API-Football rate limit hit while fetching %s (%s) — pausing enrichment for %s s; "
                "serving cached data meanwhile",
                path, reason, type(self)._af_backoff,
            )

    @classmethod
    def _af_note_rate_limited(cls):
        cls._af_backoff = min(max(60, cls._af_backoff * 2), 1800)
        cls._af_enrich_pause_until = monotonic() + cls._af_backoff
        cls._api_football_rate_limited_at = datetime.now().isoformat()

    @classmethod
    def _af_note_daily_limit(cls):
        # Pause until the next UTC midnight (API-Football's daily counter reset),
        # at least 30 min out. Convert that wall-clock reset to a process-local
        # monotonic deadline so later clock corrections cannot extend the pause.
        now_utc = datetime.now(timezone.utc)
        next_reset = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        secs = max(1800, (next_reset - now_utc).total_seconds())
        # Clear the per-minute backoff so an old minute-limit doesn't carry into
        # the next day once this daily pause elapses.
        cls._af_backoff = 0
        cls._af_enrich_pause_until = monotonic() + secs
        cls._api_football_rate_limited_at = datetime.now().isoformat()
        return secs

    @classmethod
    def _live_odds_available(cls):
        p = cls._live_odds_pause_until
        return p is None or monotonic() >= p

    @classmethod
    def _note_live_odds_result(cls, status, has_response):
        # HTTP 403 => the plan doesn't include in-play odds: back off for hours.
        if status == 403:
            cls._live_odds_pause_until = monotonic() + 6 * 60 * 60
            cls._live_odds_misses = 0
            return
        # A present response (even an all-suspended market) means the feed works.
        if has_response:
            cls._live_odds_misses = 0
            return
        # Structurally empty for several live cycles => pause for an hour.
        cls._live_odds_misses += 1
        if cls._live_odds_misses >= 5:
            cls._live_odds_pause_until = monotonic() + 60 * 60
            cls._live_odds_misses = 0

    @classmethod
    def _af_note_success(cls):
        pause = cls._af_enrich_pause_until
        # An in-flight request that started before a concurrent 429 must not
        # clear a fresh backoff — only reset once the pause window has elapsed.
        if pause is not None and monotonic() < pause:
            return
        if cls._af_backoff or pause is not None:
            cls._af_backoff = 0
            cls._af_enrich_pause_until = None

    async def _fetch_api_football_json(self, path, params=None):
        if not self._api_football_key:
            return None
        cache_key = self._api_football_cache_key(path, params or {})
        ttl = self._api_football_cache_ttl(path)
        endpoint_cache = self._runtime_dict(
            "api_endpoint_cache",
            type(self)._api_football_endpoint_cache,
        )
        endpoint_locks = self._runtime_dict(
            "api_endpoint_locks",
            type(self)._api_football_endpoint_locks,
        )
        cached = endpoint_cache.get(cache_key)
        if cached and monotonic() - cached["time"] < ttl:
            type(self)._af_stat(path)["cache_hits"] += 1
            return cached["data"]

        if self._af_enrichment_paused():
            # Rate-limited: don't make a new request; serve the last cached value
            # (even if stale) so sections don't disappear.
            return cached["data"] if cached else None

        lock = endpoint_locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            cached = endpoint_cache.get(cache_key)
            if cached and monotonic() - cached["time"] < ttl:
                type(self)._af_stat(path)["cache_hits"] += 1
                return cached["data"]
            if self._af_enrichment_paused():
                return cached["data"] if cached else None

            type(self)._af_stat(path)["calls"] += 1
            data = await self._fetch_api_football_json_uncached(path, params or {})
            if data is not None:
                endpoint_cache[cache_key] = {
                    "data": data,
                    "time": monotonic(),
                    "ttl": ttl,
                }
            return data

    async def _fetch_api_football_json_uncached(self, path, params=None):
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                f"{self.api_football_base_url}/{path}",
                headers=self._request_headers(),
                params=params or {},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                type(self)._af_stat(path)["last_status"] = response.status
                if response.status == 200:
                    raw = await response.read()
                    data = await self.hass.async_add_executor_job(json.loads, raw)
                    af_error = self._api_football_error(data)
                    if af_error:
                        # API-Football signals rate/quota limits as an HTTP 200 body
                        # error (not a 429). Treat those like a 429 so the shared
                        # enrichment backoff kicks in and stops the burst (e.g. all
                        # sensors enriching at once right after a restart).
                        if self._af_is_rate_limit_message(af_error):
                            self._af_handle_rate_limit(path, af_error)
                        else:
                            _LOGGER.warning("API-Football %s returned an error: %s", path, af_error)
                        return None
                    type(self)._af_stat(path)["last_success"] = datetime.now().isoformat()
                    self._af_note_success()
                    return data
                if response.status == 429:
                    self._af_handle_rate_limit(path, "HTTP 429")
                else:
                    _LOGGER.debug("API-Football enrichment %s returned HTTP %s", path, response.status)
        except Exception as e:
            _LOGGER.debug("Error fetching API-Football enrichment %s: %s", path, e)
        return None

    def _api_football_error(self, data):
        """Human-readable API-Football error from a 200 body, or None (also None
        for the ESPN provider, so callers can invoke it unconditionally)."""
        if self._provider != PROVIDER_API_FOOTBALL:
            return None
        from .parsers.api_football import extract_error
        return extract_error(data)

    def _api_football_body_is_auth_error(self, data):
        if self._provider != PROVIDER_API_FOOTBALL:
            return False
        from .parsers.api_football import is_auth_error
        return is_auth_error(data)

    def _handle_auth_failure(self):
        """Flag an API-Football authentication failure: set a clear status and
        start a reauth flow (once per entry) so the user can supply a new key
        without deleting the config."""
        self._auth_failed = True
        self._last_error = "API-Football API key is invalid"
        self._state = "Authentication failed"
        self._update_repairs()
        entry_id = self._config_entry_id
        if not entry_id or entry_id in type(self)._af_reauth_entries:
            return
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if not entry:
            return
        type(self)._af_reauth_entries.add(entry_id)
        _LOGGER.warning(
            "API-Football rejected the API key for %s — starting reauth", self._name
        )
        entry.async_start_reauth(self.hass)

    def _clear_auth_failure(self):
        """Reset the auth-failure marker after a successful request, so a later
        key change is picked up cleanly."""
        if self._auth_failed:
            self._auth_failed = False
        type(self)._af_reauth_entries.discard(self._config_entry_id)

    def _is_rate_limited(self):
        """Whether the provider is currently rate/quota limiting us — an active
        API-Football backoff pause, or a rate-limit message in the last error."""
        if self._provider != PROVIDER_API_FOOTBALL:
            return False
        if self._af_enrichment_paused():
            return True
        return self._af_is_rate_limit_message(self._last_error or "")

    async def _refresh_api_football_status(self):
        if self._provider != PROVIDER_API_FOOTBALL or not self._api_football_key:
            return
        status = await self._fetch_api_football_json("status")
        response = status.get("response", {}) if isinstance(status, dict) else {}
        requests = response.get("requests", {}) if isinstance(response, dict) else {}
        subscription = response.get("subscription", {}) if isinstance(response, dict) else {}
        if requests or subscription:
            self._api_football_quota = {
                "plan": subscription.get("plan"),
                "active": subscription.get("active"),
                "requests_current": requests.get("current"),
                "requests_limit_day": requests.get("limit_day"),
            }

    def _api_football_cache_key(self, path, params):
        return path, tuple(sorted((params or {}).items()))

    def _api_football_cache_ttl(self, path):
        adaptive_interval, reason = self._next_adaptive_poll()
        quota_floor = adaptive_interval if reason.startswith("quota_") else 0
        ttl = 300
        if path == "status":
            ttl = 1800
        elif path == "fixtures/events":
            ttl = 30
        elif path in {"fixtures/statistics", "fixtures/lineups"}:
            ttl = 300
        elif path == "predictions":
            ttl = 21600  # predictions change rarely; cache for 6 hours
        elif path == "injuries":
            ttl = 10800  # team news updates occasionally; cache for 3 hours
        elif path == "odds":
            ttl = 3600  # bookmaker odds update a few times a day; cache 1 hour
        elif path == "odds/live":
            ttl = 45  # in-play odds move fast; normally dedup for one live cycle
        elif path == "standings":
            ttl = 21600  # league table changes at most daily; cache for 6 hours
        elif path == "fixtures/headtohead":
            ttl = 86400  # historical meetings are immutable
        elif path in {"teams", "coachs", "players/squads", "transfers"}:
            ttl = 86400  # club profile / squad / transfers change rarely
        elif path == "players/topassists":
            ttl = 21600  # top assists change at most daily
        return max(ttl, quota_floor)

    def _prune_api_football_endpoint_cache(self, now):
        endpoint_cache = self._runtime_dict(
            "api_endpoint_cache",
            type(self)._api_football_endpoint_cache,
        )
        endpoint_locks = self._runtime_dict(
            "api_endpoint_locks",
            type(self)._api_football_endpoint_locks,
        )
        fresh = {
            k: v for k, v in endpoint_cache.items()
            if now - v["time"] < v.get("ttl", 300)
        }
        endpoint_cache.clear()
        endpoint_cache.update(fresh)
        for key, lock in tuple(endpoint_locks.items()):
            if key not in endpoint_cache and not lock.locked():
                endpoint_locks.pop(key, None)
