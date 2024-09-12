import logging
import aiohttp
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    try:
        api_key = entry.data.get("api_key")
        competition_name = entry.data.get("name")
        competition_code = entry.data.get("competition_code")
        team_id = entry.data.get("team_id")
        name_prefix = entry.data.get("name")

        sensors = []

        # Inizializza hass.data[DOMAIN] se non esiste
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}

        # Evita la duplicazione del sensore calciolive_competizioni
        if "calciolive_competizioni" not in hass.data[DOMAIN] and competition_code:
            sensors.append(CalcioLiveSensor(hass, f"calciolive_competizioni", api_key, competition_code, "competitions"))
            hass.data[DOMAIN]["calciolive_competizioni"] = True
        
        if competition_code:
            # Crea i sensori relativi alle competizioni
            sensors += [
                CalcioLiveSensor(hass, f"calciolive_{competition_name}_classifica", api_key, competition_code, "standings"),
                CalcioLiveSensor(hass, f"calciolive_{competition_name}_match_day", api_key, competition_code, "match_day"),
                CalcioLiveSensor(hass, f"calciolive_{competition_name}_cannonieri", api_key, competition_code, "scorers")
            ]

        if team_id:
            # Crea il sensore per la squadra
            sensors.append(CalcioLiveSensor(hass, f"calciolive_{competition_name}", api_key, team_id, "team_matches", team_id=team_id))

        async_add_entities(sensors, True)

    except Exception as e:
        _LOGGER.error(f"Errore durante la configurazione dei sensori: {e}")



class CalcioLiveSensor(Entity):
    def __init__(self, hass, name, api_key, competition_code=None, sensor_type=None, team_id=None):
        self.hass = hass
        self._name = name
        self._api_key = api_key
        self._competition_code = competition_code
        self._team_id = team_id
        self._sensor_type = sensor_type
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    async def async_update(self):
        url = await self._build_url()
        headers = {"X-Auth-Token": self._api_key}

        if url is None:
            _LOGGER.error(f"URL is None for {self._name}")
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Errore HTTP {response.status} per {self._name}")
                        return
                    data = await response.json()
                    self._process_data(data)
        except aiohttp.ClientError as error:
            _LOGGER.error(f"Errore nel recupero dei dati per {self._name}: {error}")
            self._state = None

    async def _build_url(self):
        """Construct the URL for the API based on the sensor type."""
        base_url = "https://api.football-data.org/v4"
        competitions_url      = f"{base_url}/competitions"
        competition_sp_url    = f"{base_url}/competitions/{self._competition_code}"
        standings_url         = f"{base_url}/competitions/{self._competition_code}/standings?season=2024"
        scorers_url           = f"{base_url}/competitions/{self._competition_code}/scorers"
        match_url             = f"{base_url}/competitions/{self._competition_code}/matches?matchday="
        match_team_url        = f"{base_url}/teams/{self._team_id}/matches"
        
        if self._sensor_type == "competitions":
            return competitions_url
        
        elif self._sensor_type == "standings":
            return standings_url
        
        elif self._sensor_type == "match_day":
            headers = {"X-Auth-Token": self._api_key}

            # Ottieni il matchday dai dati delle standings
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(competition_sp_url, headers=headers) as response:
                        if response.status != 200:
                            _LOGGER.error(f"Errore HTTP {response.status} nel recuperare le standings")
                            return None

                        data = await response.json()

                        # Ottieni il matchday da currentSeason
                        current_matchday = data.get("currentSeason", {}).get("currentMatchday")
                        #_LOGGER.error(f" dati rilevati {data} {current_matchday}")
                        
                        if current_matchday:
                            #_LOGGER.error(f"{match_url}{current_matchday}")
                            return f"{match_url}{current_matchday}"
                        else:
                            _LOGGER.error(f"Errore: impossibile ottenere il currentMatchday dalle API {current_matchday}")
                            return None
            
                except aiohttp.ClientError as error:
                    _LOGGER.error(f"Errore nel recuperare le standings: {error}")
                    return None
        
        elif self._sensor_type == "scorers":
            return scorers_url
        
        elif self._sensor_type == "team_matches" and self._team_id:
            return match_team_url
        
        return None

    def _process_data(self, data):
        if self._sensor_type == "competitions":
            self._state = len(data.get("competitions", []))
            self._attributes = {"competitions": data.get("competitions", [])}

        elif self._sensor_type == "standings":
            current_matchday = data.get("season", {}).get("currentMatchday", "N/A")
            self._state = f"Giornata {current_matchday}"
            self._attributes = {
                "competition": data.get("competition", {}),
                "season": data.get("season", {}),
                "standings": data.get("standings", []),
                "area": data.get("area", {}),
                "filters": data.get("filters", {}),
                "current_matchday": current_matchday
            }

        elif self._sensor_type == "match_day":
            matchday = data.get("filters", {}).get("matchday", "N/A")
            matches = data.get("matches", [])
            self._state = f"Giornata {matchday}"
            self._attributes = {
                "matchday": matchday,
                "result_set": data.get("resultSet", {}),
                "competition": data.get("competition", {}),
                "matches": matches
            }

        elif self._sensor_type == "scorers":
            self._state = data.get("count")
            self._attributes = {
                "competition": data.get("competition", {}),
                "season": data.get("season", {}),
                "scorers": data.get("scorers", [])
            }

        elif self._sensor_type == "team_matches":
            result_set = data.get("resultSet", {})
            matches = data.get("matches", [])

            # Stato: numero di partite giocate
            self._state = result_set.get("played", 0)

            # Attributi: dettagli delle partite e altre informazioni
            self._attributes = {
                "count": result_set.get("count", 0),
                "first_match_date": result_set.get("first", "N/A"),
                "last_match_date": result_set.get("last", "N/A"),
                "wins": result_set.get("wins", 0),
                "draws": result_set.get("draws", 0),
                "losses": result_set.get("losses", 0),
                "matches": []
            }

            # Elaborazione delle singole partite
            for match in matches:
                self._attributes["matches"].append({
                    "competition_name": match.get("competition", {}).get("name", "N/A"),
                    "competition_code": match.get("competition", {}).get("code", "N/A"),
                    "matchday": match.get("matchday", "N/A"),
                    "home_team": match.get("homeTeam", {}).get("name", "N/A"),
                    "away_team": match.get("awayTeam", {}).get("name", "N/A"),
                    "home_team_crest": match.get("homeTeam", {}).get("crest", ""),
                    "away_team_crest": match.get("awayTeam", {}).get("crest", ""),
                    "score_full_time": match.get("score", {}).get("fullTime", {}),
                    "utc_date": match.get("utcDate", "N/A"),
                    "status": match.get("status", "N/A"),
                })
