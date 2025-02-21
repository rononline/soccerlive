import asyncio
import aiohttp
from datetime import datetime, timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import random
from .const import DOMAIN, _LOGGER

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    try:
        competition_name = entry.data.get("name")
        competition_code = entry.data.get("competition_code")
        team_name = entry.data.get("team_name")
        selection = entry.data.get("selection")
        team_id = entry.data.get("team_id")
        #_LOGGER.error(f"LOG DATA: {entry.data}")
        #{'competition_code': 'uefa.champions', 'end_date': '2025-07-26', 'name': 'Team UEFA Champions League Internazionale', 'selection': 'Team', 'start_date': '2024-11-27', 'team_name': 'Internazionale'}
        
        start_date = entry.options.get("start_date", datetime.now().strftime("%Y-%m-%d"))
        end_date = entry.options.get("end_date", (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"))

        base_scan_interval = timedelta(minutes=entry.options.get("scan_interval", 3))
        sensors = []

        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}

        if team_name:
            team_name_normalized = team_name.replace(" ", "_").replace(".", "_").lower()
            competition_name = competition_code.replace(" ", "_").replace(".", "_").lower()

            sensors += [
                CalcioLiveSensor(
                    hass, f"calciolive_next_{competition_name}_{team_name_normalized}", competition_code, "team_match",
                    base_scan_interval + timedelta(seconds=random.randint(0, 30)), team_name=team_name,
                    config_entry_id=entry.entry_id, start_date=start_date, end_date=end_date, team_id=team_id
                ),
                CalcioLiveSensor(
                    hass, f"calciolive_all_{competition_name}_{team_name_normalized}", competition_code, "team_matches",
                    base_scan_interval + timedelta(seconds=random.randint(0, 30)), team_name=team_name,
                    config_entry_id=entry.entry_id, start_date=start_date, end_date=end_date, team_id=team_id
                ),
                CalcioLiveSensor(
                    hass, f"calciolive_all_mixed_{team_name_normalized}", competition_code, "team_matches_mixed",
                    base_scan_interval + timedelta(seconds=random.randint(0, 30)), team_name=team_name,
                    config_entry_id=entry.entry_id, start_date=start_date, end_date=end_date, team_id=team_id
                )
            ]

        elif competition_code:
            competition_name = competition_name.replace(" ", "_").replace(".", "_").lower()

            sensors += [
                CalcioLiveSensor(
                    hass, f"calciolive_classifica_{competition_name}", competition_code, "standings",
                    base_scan_interval + timedelta(seconds=random.randint(0, 30)), config_entry_id=entry.entry_id,
                    start_date=start_date, end_date=end_date, team_id=team_id
                ),
                CalcioLiveSensor(
                    hass, f"calciolive_all_{competition_name}", competition_code, "match_day",
                    base_scan_interval + timedelta(seconds=random.randint(0, 30)), config_entry_id=entry.entry_id,
                    start_date=start_date, end_date=end_date, team_id=team_id
                )
            ]

        async_add_entities(sensors, True)

    except Exception as e:
        _LOGGER.error(f"Errore durante la configurazione dei sensori: {e}")


class CalcioLiveSensor(Entity):
    _cache = {}

    def __init__(self, hass, name, code, sensor_type=None, scan_interval=timedelta(minutes=5),
                 team_name=None, config_entry_id=None, start_date=None, end_date=None, team_id=None):
        self.hass = hass
        self._name = name
        self._code = code
        self._team_id = team_id
        self._sensor_type = sensor_type
        self._scan_interval = scan_interval
        self._state = None
        self._attributes = {}
        self._config_entry_id = config_entry_id
        self._team_name = team_name
        today = datetime.now()
        self._start_date = (today - relativedelta(months=3)).strftime("%Y-%m-%d") if not start_date else start_date
        self._end_date = (today + relativedelta(months=4)).strftime("%Y-%m-%d") if not end_date else end_date
        self._start_date = datetime.strptime(self._start_date, "%Y-%m-%d")
        self._end_date = datetime.strptime(self._end_date, "%Y-%m-%d")
        
        self._request_count = 0
        self._last_request_time = None

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {
            **self._attributes,
            "request_count": self._request_count,
            "last_request_time": self._last_request_time,
            "start_date": self._start_date.strftime("%Y-%m-%d"),
            "end_date": self._end_date.strftime("%Y-%m-%d"),
        }

    @property
    def should_poll(self):
        return True

    @property
    def unique_id(self):
        return f"{self._name}_{self._sensor_type}"

    @property
    def config_entry_id(self):
        return self._config_entry_id

    async def async_update(self):
        _LOGGER.info(f"Starting update for {self._name}")

        cache_key = f"{self._sensor_type}_{self._code}_{self._team_name}"
        if cache_key in CalcioLiveSensor._cache and (datetime.now() - CalcioLiveSensor._cache[cache_key]["time"]).seconds < 60:
            self._process_data(CalcioLiveSensor._cache[cache_key]["data"])
            _LOGGER.info(f"Using cached data for {self._name}")
            return

        url = await self._build_url()

        if url is None:
            return

        retries = 0
        while retries < 3:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            _LOGGER.debug(f"Data received for {self._name}: {data}")
                            CalcioLiveSensor._cache[cache_key] = {"data": data, "time": datetime.now()}
                            self._process_data(data)
                            _LOGGER.info(f"Finished update for {self._name}")
                            break
                        else:
                            await asyncio.sleep(5)
                            retries += 1
            except aiohttp.ClientError as error:
                await asyncio.sleep(5)
                retries += 1
            except asyncio.TimeoutError:
                await asyncio.sleep(5)
                retries += 1

    async def _build_url(self):
        season_data = await self._get_season_data()

        season_start = season_data.get("startDate", "2024-08-01").replace("-", "")
        season_end = season_data.get("endDate", "2025-07-01").replace("-", "")

        base_url = "https://site.web.api.espn.com/apis/v2/sports/soccer"
        base_url_2 = "https://site.api.espn.com/apis/site/v2/sports/soccer"
        base_url_3  = "https://site.web.api.espn.com/apis/site/v2/sports/soccer"

        standings_url = f"{base_url}/{self._code}/standings?"
        match_day_url = f"{base_url_2}/{self._code}/scoreboard?limit=100&dates={self._start_date.strftime('%Y%m%d')}-{self._end_date.strftime('%Y%m%d')}"
        team_url_schedule = f"{base_url_2}/{self._code}/scoreboard?limit=1000&dates={season_start}-{season_end}"
        team_url_schedule_mixed = f"{base_url_3}/all/teams/{self._team_id}/schedule?fixture=true"

        if self._sensor_type == "standings":
            return standings_url
        elif self._sensor_type == "match_day":
            return match_day_url
        elif self._sensor_type == "team_matches" and self._team_name:
            return team_url_schedule
        elif self._sensor_type == "team_match" and self._team_name:
            return match_day_url
        elif self._sensor_type == "team_matches_mixed" and self._team_name:
            return team_url_schedule_mixed
        return None

    async def _get_season_data(self):
        url = f"https://site.web.api.espn.com/apis/v2/sports/soccer/{self._code}/standings"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("season", {})
        except Exception as e:
            _LOGGER.error(f"Errore durante il caricamento dei dati della stagione: {e}")
            return {}

    def _process_data(self, data):
        from .sensori.scoreboard import process_match_data

        if self._sensor_type == "standings":
            from .sensori.classifica import classifica_data
            processed_data = classifica_data(data)
            self._state = "Classifica"
            self._attributes = processed_data

        elif self._sensor_type == "match_day":
            match_data = process_match_data(data, self.hass, start_date=self._start_date.strftime("%Y-%m-%d"),
                                            end_date=self._end_date.strftime("%Y-%m-%d"))
            self._state = "Matches of the Week"
            self._attributes = {
                "league_info": match_data.get("league_info", "N/A"),
                "matches": match_data.get("matches", [])
            }

        elif self._sensor_type in ["team_matches", "team_match", "team_matches_mixed"]:
            def get_team_match_data(next_match_only=False):
                return process_match_data(
                    data, self.hass, team_name=self._team_name, next_match_only=next_match_only,
                    start_date=self._start_date.strftime("%Y-%m-%d"), end_date=self._end_date.strftime("%Y-%m-%d")
                )

            if self._sensor_type in ["team_matches", "team_matches_mixed"]:
                match_data = get_team_match_data()
                matches = match_data.get("matches", [])
                if matches:
                    live_matches = [m for m in matches if m["state"] == "in"]
                    if live_matches:
                        self._state = f"{live_matches[0]['home_score']} - {live_matches[0]['away_score']} ({live_matches[0]['clock']})"
                    else:
                        self._state = f"{len(matches)} partite per {match_data.get('team_name', 'N/A')}"
                self._attributes = {
                    "league_info": match_data.get("league_info", "N/A"),
                    "team_name": match_data.get("team_name", "N/A"),
                    "team_logo": match_data.get("team_logo", "N/A"),
                    "matches": matches
                }

            elif self._sensor_type == "team_match":
                team_match = get_team_match_data(next_match_only=True)
                matches = team_match.get("matches", [])
                if matches:
                    live_matches = [m for m in matches if m["state"] == "in"]
                    if live_matches:
                        next_match = live_matches[0]
                        self._state = f"{next_match['home_score']} - {next_match['away_score']} ({next_match['clock']})"
                    else:
                        next_match = matches[0]
                        self._state = f"Prossimo match: {next_match.get('home_team', 'N/A')} vs {next_match.get('away_team', 'N/A')}"
                    self._attributes = team_match
                else:
                    self._state = "Nessuna partita disponibile"
                    self._attributes = team_match
    
            
