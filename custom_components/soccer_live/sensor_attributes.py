"""Match-attribute computation for :class:`SoccerLiveSensor`.

This mixin groups the ``_compute_*`` helpers that turn parsed match data into
the flat attribute dictionaries exposed by the sensor. They are pure instance
methods (no shared class state), split out of ``sensor.py`` to keep that module
smaller.
"""

from datetime import datetime, timezone


class MatchAttributesMixin:
    def _compute_next_match_attributes(self, match):
        """Compute attributes for the next/current match."""
        if not match:
            return {}
        
        match_datetime = self._parse_match_datetime(match.get("date"))
        
        broadcasts = match.get("broadcasts") or []
        if not isinstance(broadcasts, list):
            broadcasts = [broadcasts] if broadcasts and broadcasts != "N/A" else []
        return {
            "next_match_home_team": match.get("home_team", "N/A"),
            "next_match_away_team": match.get("away_team", "N/A"),
            "next_match_home_abbrev": match.get("home_abbrev", "N/A"),
            "next_match_away_abbrev": match.get("away_abbrev", "N/A"),
            "next_match_home_logo": match.get("home_logo", "N/A"),
            "next_match_away_logo": match.get("away_logo", "N/A"),
            "next_match_home_color": match.get("home_color", "N/A"),
            "next_match_away_color": match.get("away_color", "N/A"),
            "home_color": match.get("home_color", "N/A"),
            "away_color": match.get("away_color", "N/A"),
            "team_colors": [
                color for color in (match.get("home_color"), match.get("away_color"))
                if color and color != "N/A"
            ],
            "next_match_home_score": match.get("home_score", "N/A"),
            "next_match_away_score": match.get("away_score", "N/A"),
            "next_match_date": match.get("date", "N/A"),
            "next_match_datetime_iso": match_datetime.isoformat() if match_datetime else "N/A",
            "next_match_minutes_until": self._get_minutes_until(match_datetime),
            "next_match_status": match.get("state", "N/A"),
            "next_match_description": match.get("status", "N/A"),
            "next_match_venue": match.get("venue", "N/A"),
            "next_match_period": match.get("period", "N/A"),
            "next_match_clock": match.get("clock", "N/A"),
            "next_match_home_form": match.get("home_form", "N/A"),
            "next_match_away_form": match.get("away_form", "N/A"),
            "next_match_season_info": match.get("season_info", "N/A"),
            "next_match_broadcasts": broadcasts,
            "next_match_attendance": match.get("attendance", "N/A"),
            "next_match_neutral_site": match.get("neutral_site", False),
            "next_match_has_stats": bool(match.get("has_stats") or match.get("home_statistics")),
            "next_match_has_commentary": bool(match.get("has_commentary") or match.get("key_events")),
            "next_match_event_id": match.get("event_id", "N/A"),
            "next_match_broadcast_count": len(broadcasts),
            "next_match_event_count": len(match.get("match_details") or []),
            "next_match_h2h_count": len(match.get("head_to_head") or []),
            "next_match_links": match.get("links") or [],
            "next_match_week": match.get("week_number", "N/A"),
        }

    def _compute_live_match_attributes(self, matches):
        """Compute attributes for the live match, if one exists."""
        live_matches = [m for m in matches if m.get("state") == "in"]
        if not live_matches:
            return {}
        
        match = live_matches[0]
        return {
            "live_match_home_team": match.get("home_team", "N/A"),
            "live_match_away_team": match.get("away_team", "N/A"),
            "live_match_home_abbrev": match.get("home_abbrev", "N/A"),
            "live_match_away_abbrev": match.get("away_abbrev", "N/A"),
            "live_match_home_logo": match.get("home_logo", "N/A"),
            "live_match_away_logo": match.get("away_logo", "N/A"),
            "live_match_home_color": match.get("home_color", "N/A"),
            "live_match_away_color": match.get("away_color", "N/A"),
            "home_color": match.get("home_color", "N/A"),
            "away_color": match.get("away_color", "N/A"),
            "team_colors": [
                color for color in (match.get("home_color"), match.get("away_color"))
                if color and color != "N/A"
            ],
            "live_match_home_score": match.get("home_score", "N/A"),
            "live_match_away_score": match.get("away_score", "N/A"),
            "live_match_date": match.get("date", "N/A"),
            "live_match_status": "in",
            "live_match_description": match.get("status", "N/A"),
            "live_match_venue": match.get("venue", "N/A"),
            "live_match_period": match.get("period", "N/A"),
            "live_match_clock": match.get("clock", "N/A"),
            "live_match_home_form": match.get("home_form", "N/A"),
            "live_match_away_form": match.get("away_form", "N/A"),
            "live_match_event_id": match.get("event_id", "N/A"),
            "live_match_event_count": len(match.get("match_details") or []),
            "live_match_h2h_count": len(match.get("head_to_head") or []),
        }

    def _compute_all_matches_attributes(self, matches, events: list | None = None, detect_events=True):
        if events is None:
            events = []
        if detect_events and self._sensor_type != "team_matches_mixed":
            self._detect_and_dispatch_goals(matches, events)
            self._detect_and_dispatch_cards(matches, events)
            self._detect_and_dispatch_match_finished(matches, events)
            self._detect_and_dispatch_match_started(matches, events)
        
        computed = {}
        
        # Info match in corso se esiste
        live_matches = [m for m in matches if m.get("state") == "in"]
        if live_matches:
            computed.update(self._compute_live_match_attributes(matches))
            computed["has_live_match"] = True
        else:
            computed["has_live_match"] = False
        
        # Upcoming match info
        upcoming_matches = [m for m in matches if m.get("state") == "pre"]
        if upcoming_matches:
            computed.update(self._compute_next_match_attributes(upcoming_matches[0]))
            computed["has_upcoming_match"] = True
        else:
            computed["has_upcoming_match"] = False
        
        # Most recent finished match (within recent_match_hours window)
        from .parsers.scoreboard import is_within_recent_window
        recent_finished_matches = [m for m in matches
            if m.get("state") == "post" and is_within_recent_window(m.get("date"), self._recent_match_hours)
        ]
        if recent_finished_matches:
            last_match = recent_finished_matches[-1]  # ESPN chronological: [-1] is most recent
            computed.update({
                "last_match_home_team": last_match.get("home_team", "N/A"),
                "last_match_away_team": last_match.get("away_team", "N/A"),
                "last_match_home_logo": last_match.get("home_logo", "N/A"),
                "last_match_away_logo": last_match.get("away_logo", "N/A"),
                "last_match_home_score": last_match.get("home_score", "N/A"),
                "last_match_away_score": last_match.get("away_score", "N/A"),
                "last_match_date": last_match.get("date", "N/A"),
                "last_match_venue": last_match.get("venue", "N/A"),
                "has_recent_match": True,
            })
        else:
            computed["has_recent_match"] = False
        
        # Conteggi
        computed["total_matches"] = len(matches)
        computed["live_matches_count"] = len(live_matches)
        computed["upcoming_matches_count"] = len(upcoming_matches)
        computed["finished_matches_count"] = len([m for m in matches if m.get("state") == "post"])
        computed.update(self._compute_schedule_summary(matches))
        
        return computed

    def _compute_schedule_summary(self, matches):
        """Return compact, deduplicated schedule slices for cards and automations."""
        unique_matches = []
        seen = set()
        for match in matches or []:
            key = match.get("event_id") or f"{match.get('date')}|{match.get('home_team')}|{match.get('away_team')}"
            if key in seen:
                continue
            seen.add(key)
            unique_matches.append(match)

        def sort_key(match):
            parsed = self._parse_match_datetime(match.get("date"))
            return parsed or datetime.max.replace(tzinfo=timezone.utc)

        unique_matches = sorted(unique_matches, key=sort_key)
        live = [m for m in unique_matches if m.get("state") == "in"]
        upcoming = [m for m in unique_matches if m.get("state") == "pre"]
        recent = [m for m in unique_matches if m.get("state") == "post"][-5:]

        def compact(match):
            item = {
                "event_id": match.get("event_id"),
                "date": match.get("date"),
                "state": match.get("state"),
                "clock": match.get("clock"),
                "home_team": match.get("home_team"),
                "home_abbrev": match.get("home_abbrev"),
                "home_logo": match.get("home_logo"),
                "home_color": match.get("home_color"),
                "home_score": match.get("home_score"),
                "away_team": match.get("away_team"),
                "away_abbrev": match.get("away_abbrev"),
                "away_logo": match.get("away_logo"),
                "away_color": match.get("away_color"),
                "away_score": match.get("away_score"),
                "venue": match.get("venue"),
                "league_name": match.get("league_name"),
                "league_logo": match.get("league_logo"),
                "season_info": match.get("season_info"),
                "broadcasts": match.get("broadcasts") or [],
            }
            for key in (
                "match_details",
                "key_events",
                "home_statistics",
                "away_statistics",
                "lineup_home",
                "lineup_away",
                "formation_home",
                "formation_away",
            ):
                value = match.get(key)
                if value:
                    item[key] = value
            return item

        return {
            "schedule_match_count": len(unique_matches),
            "schedule_live_count": len(live),
            "schedule_upcoming_count": len(upcoming),
            "schedule_recent_count": len(recent),
            "schedule_live_matches": [compact(m) for m in live[:5]],
            "schedule_upcoming_matches": [compact(m) for m in upcoming[:10]],
            "schedule_recent_matches": [compact(m) for m in list(reversed(recent))],
        }
