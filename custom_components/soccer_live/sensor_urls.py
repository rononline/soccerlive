"""ESPN URL building and the cross-year scoreboard-merge strategy for the
Soccer Live sensor, split out of sensor.py as a mixin.

ESPN's ``/scoreboard?dates=YYYY`` is a *calendar-year* query, so a season that
runs Aug–May spans two of them. These helpers build the primary
scoreboard/fixtures URL, work out which calendar years a season covers, and
merge the extra years' events back into the primary response.
``SoccerLiveSensor`` inherits the mixin, so the methods resolve ``self.*`` (base
URLs, competition code, the calendar fetch, the API-Football URL builder, the
request headers) across the combined class via the MRO.
"""

import asyncio
import json
from datetime import datetime

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PROVIDER_API_FOOTBALL

# Sensor types whose scoreboard/fixtures request covers a date range (and so can
# span two calendar years); others hit single, dateless ESPN endpoints.
_DATE_RANGE_SENSOR_TYPES = {"match_day", "team_match", "team_matches"}


class SoccerLiveUrlMixin:
    """URL building + cross-year scoreboard merge for ``SoccerLiveSensor``."""

    async def _build_url(self):
        if self._provider == PROVIDER_API_FOOTBALL:
            return self._build_api_football_url()

        # ESPN's /scoreboard?dates=YYYY is a *calendar-year* query, so a season
        # that runs Aug–May spans two of them. Extra years to fetch and merge
        # into the primary response are collected here (reset every build).
        self._secondary_scoreboard_urls = []

        season_start = ""
        season_end = ""

        # Sensors below do not need the competition calendar. Return early to
        # avoid a burst of unnecessary calendar calls during Home Assistant
        # startup or reloads.
        if self._sensor_type == "news":
            return f"{self.base_url_2}/{self._code}/news?limit=15"

        if self._sensor_type == "top_scorers":
            return f"{self.base_url_2}/{self._code}/leaders"

        if self._sensor_type == "bracket":
            # Bracket covers the full KO phase (Feb-Jul).
            # If we are in the second half of the season (Feb-Jul) use current year,
            # otherwise use next year (the KO phase always falls in the second half).
            from datetime import datetime as _dt
            now = _dt.now()
            if now.month >= 8:
                ko_year = now.year + 1
            else:
                ko_year = now.year
            # ESPN stopped accepting dates=start-end ranges (returns HTTP 400),
            # and dates=YYYY is a calendar-year query. A European KO season runs
            # Aug (ko_year-1) through May/Jun (ko_year), so the group stage lives
            # in calendar year ko_year-1 and the knockout ties in ko_year. Fetch
            # both and merge, then let the bracket parser pick out the KO ties.
            self._secondary_scoreboard_urls = [
                f"{self.base_url_3}/{self._code}/scoreboard?limit=300&dates={ko_year}"
            ]
            return f"{self.base_url_3}/{self._code}/scoreboard?limit=300&dates={ko_year - 1}"

        if self._sensor_type == "standings":
            return f"{self.base_url}/{self._code}/standings?"

        if self._sensor_type == "team_matches_mixed" and self._team_name:
            return f"{self.base_url_3}/all/teams/{self._team_id}/schedule?fixture=true"

        if self._sensor_type == "all_matches_today":
            return f"{self.base_url_2}/all/scoreboard"

        if self._code and self._sensor_type in _DATE_RANGE_SENSOR_TYPES:
            season_start, season_end = await self._get_calendar_data()

        # Store dynamic dates for use in _process_data so match filtering
        # follows the current season automatically without manual yearly updates.
        if season_start and season_end:
            try:
                self._dyn_start_date = datetime.strptime(season_start[:10], "%Y-%m-%d")
                self._dyn_end_date = datetime.strptime(season_end[:10], "%Y-%m-%d")
            except (ValueError, TypeError):
                pass

        # Fall back to static dates if ESPN did not return calendar dates.
        # Empty filters are valid, so omit the date range when neither source
        # provides a complete range.
        if not season_start or not season_end:
            if self._start_date and self._end_date:
                season_start = self._start_date.strftime("%Y-%m-%d")
                season_end = self._end_date.strftime("%Y-%m-%d")
            else:
                season_start = ""
                season_end = ""

        if season_start and season_end:
            season_start = season_start[:10].replace("-", "")
            season_end = season_end[:10].replace("-", "")

        if self._sensor_type in _DATE_RANGE_SENSOR_TYPES:
            url = f"{self.base_url_3}/{self._code}/scoreboard?limit=1000"
            # ESPN stopped accepting dates=start-end ranges (returns HTTP 400);
            # dates=YYYY returns that *calendar year*. A season running Aug–May
            # spans two calendar years, so fetch each year it covers and merge
            # them (the response is still filtered to _dyn_start_date/
            # _dyn_end_date in _process_data).
            years = self._scoreboard_years(season_start, season_end)
            if years:
                url += f"&dates={years[0]}"
                self._secondary_scoreboard_urls = [
                    f"{self.base_url_3}/{self._code}/scoreboard?limit=1000&dates={y}"
                    for y in years[1:]
                ]
            return url

        return None

    @staticmethod
    def _scoreboard_years(season_start, season_end):
        """Calendar years a season spans, as strings, for ESPN dates=YYYY.

        ``season_start``/``season_end`` are ``YYYYMMDD`` strings (or empty).
        A soccer season runs Aug–May, so it usually covers two calendar years;
        single-calendar-year leagues (e.g. MLS) return just one. With no season
        info, falls back to the current calendar year so the scoreboard still
        returns the whole year (incl. upcoming fixtures) instead of only today.
        """
        if not season_start:
            return [str(datetime.now().year)]
        start_year = int(season_start[:4])
        end_year = int(season_end[:4]) if season_end else start_year
        if end_year < start_year:
            end_year = start_year
        # A season never spans more than two calendar years; cap defensively.
        end_year = min(end_year, start_year + 1)
        return [str(year) for year in range(start_year, end_year + 1)]

    async def _merge_secondary_scoreboards(self, data):
        """Merge extra calendar-year scoreboards into the primary response.

        ESPN's dates=YYYY only returns one calendar year, so a cross-year
        season needs its remaining year(s) fetched and their ``events`` folded
        in (deduplicated by event id). Best-effort: any secondary fetch that
        fails is skipped, leaving the primary response intact.
        """
        urls = getattr(self, "_secondary_scoreboard_urls", None)
        if not urls or not isinstance(data, dict):
            return data
        events = data.get("events")
        if not isinstance(events, list):
            return data
        seen = {e.get("id") for e in events if isinstance(e, dict)}
        session = async_get_clientsession(self.hass)
        headers = self._request_headers()
        for extra_url in urls:
            try:
                async with session.get(
                    extra_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        continue
                    raw = await response.read()
                    extra = await self.hass.async_add_executor_job(json.loads, raw)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, UnicodeDecodeError):
                continue
            if not isinstance(extra, dict):
                continue
            for event in extra.get("events") or []:
                if isinstance(event, dict) and event.get("id") not in seen:
                    events.append(event)
                    seen.add(event.get("id"))
        return data
