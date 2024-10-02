import asyncio
import aiohttp
from datetime import timedelta, datetime
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
        team_id = entry.data.get("team_id")

        base_scan_interval = timedelta(minutes=entry.options.get("scan_interval", 3))
        sensors = []

        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}

        if team_id:
            team_name = competition_name.replace(" ", "_").lower()
            
            sensors += [
                CalcioLiveSensor(
                    hass, f"calciolive_{team_name}_next".lower(), competition_code, "team_match", base_scan_interval, team_id=team_id, config_entry_id=entry.entry_id
                ),
                CalcioLiveSensor(
                    hass, f"calciolive_{team_name}".lower(), competition_code, "team_matches", base_scan_interval, team_id=team_id, config_entry_id=entry.entry_id
                )
            ]


        # Se c'è il competition_code, creiamo solo i sensori "classifica" e "match_day"
        elif competition_code:
            sensors += [
                CalcioLiveSensor(
                    hass, f"calciolive_{competition_name}_classifica".replace(" ", "_").lower(), competition_code, "standings", base_scan_interval + timedelta(seconds=random.randint(0, 30)), config_entry_id=entry.entry_id
                ),
                CalcioLiveSensor(
                    hass, f"calciolive_{competition_name}_match_day".replace(" ", "_").lower(), competition_code, "match_day", base_scan_interval + timedelta(seconds=random.randint(0, 30)), config_entry_id=entry.entry_id
                )
            ]

        async_add_entities(sensors, True)

    except Exception as e:
        _LOGGER.error(f"Errore durante la configurazione dei sensori: {e}")




class CalcioLiveSensor(Entity):
    _cache = {}

    def __init__(self, hass, name, code, sensor_type=None, scan_interval=timedelta(minutes=5), team_id=None, config_entry_id=None):
        self.hass = hass
        self._name = name
        self._code = code
        self._sensor_type = sensor_type
        self._scan_interval = scan_interval
        self._state = None
        self._attributes = {}
        self._config_entry_id = config_entry_id
        self._team_id = team_id
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
            "last_request_time": self._last_request_time
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

        cache_key = f"{self._sensor_type}_{self._code}_{self._team_id}"
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
        start_date, end_date = self._get_week_range()
        
        base_url   = "https://site.web.api.espn.com/apis/v2/sports/soccer"
        base_url_2 = "https://site.api.espn.com/apis/site/v2/sports/soccer"
        standings_url = f"{base_url}/{self._code}/standings?season=2024" #classifica
        match_day_url = f"{base_url_2}/{self._code}/scoreboard?dates={start_date}-{end_date}&limit=100" #partite della settimana
        team_url = f"{base_url_2}/{self._code}/teams/{self._team_id}" #team squadra
        team_url_schedule = f"{base_url_2}/{self._code}/teams/{self._team_id}/schedule" #team squadra

        if self._sensor_type == "standings":
            return standings_url
        elif self._sensor_type == "match_day":
            return match_day_url
        elif self._sensor_type == "team_match" and self._team_id:
            return team_url
        elif self._sensor_type == "team_matches" and self._team_id:
            return team_url_schedule
        return None
    
    def _get_week_range(self):
        today = datetime.now()
        start_of_period = today - timedelta(days=today.weekday() + 3)  # Inizio 3 giorni prima
        end_of_period = today + timedelta(days=(7 - today.weekday()))  # Fine Lunedì della settimana successiva
        return start_of_period.strftime('%Y%m%d'), end_of_period.strftime('%Y%m%d')

    
    def _process_data(self, data):
        if self._sensor_type == "standings":
            from .sensori.classifica import classifica_data
            
            processed_data = classifica_data(data)
            self._state = f"Classifica Serie A"
            self._attributes = processed_data

        elif self._sensor_type == "match_day":
            from .sensori.match_day import match_day_data
            
            matches = match_day_data(data)
            self._state = "Matches of the Week"
            self._attributes = matches

        elif self._sensor_type == "team_matches":
            from .sensori.team_matches import team_matches_data
            
            match_data = team_matches_data(data)
            self._state = f"Prossime {len(match_data['matches'])} partite"
            self._attributes = {
                "team_name": match_data["team_name"],
                "team_logo": match_data["team_logo"],
                "matches": match_data["matches"]
            }
        
           
        elif self._sensor_type == "team_match":
            from .sensori.team_match import team_match_data
            
            team_match = team_match_data(data)
            self._state = f"Prossimo match: {team_match.get('home_team', 'N/A')} vs {team_match.get('away_team', 'N/A')}"
            self._attributes = team_match
        
        
        

