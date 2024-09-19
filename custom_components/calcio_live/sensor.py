import asyncio
import logging
import aiohttp
from datetime import timedelta, datetime
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

semaphore = asyncio.Semaphore(30)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    try:
        api_key = entry.data.get("api_key")
        competition_name = entry.data.get("name")
        competition_code = entry.data.get("competition_code")
        team_id = entry.data.get("team_id")
        scan_interval = timedelta(minutes=entry.options.get("scan_interval", 10))

        sensors = []

        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}

        if "calciolive_competizioni" not in hass.data[DOMAIN] and competition_code:
            sensors.append(CalcioLiveSensor(hass, f"calciolive_competizioni", api_key, competition_code, "competitions", scan_interval))
            hass.data[DOMAIN]["calciolive_competizioni"] = True

        if "calciolive_matchof_day" not in hass.data[DOMAIN] and competition_code:
            sensors.append(CalcioLiveSensor(hass, f"calciolive_matchof_day", api_key, competition_code, "matchof_day", scan_interval))
            hass.data[DOMAIN]["calciolive_matchof_day"] = True

        if competition_code:
            sensors += [
                CalcioLiveSensor(hass, f"calciolive_{competition_name}_classifica", api_key, competition_code, "standings", scan_interval),
                CalcioLiveSensor(hass, f"calciolive_{competition_name}_match_day", api_key, competition_code, "match_day", scan_interval),
                CalcioLiveSensor(hass, f"calciolive_{competition_name}_cannonieri", api_key, competition_code, "scorers", scan_interval)
            ]

        if team_id:
            sensors.append(CalcioLiveSensor(hass, f"calciolive_{competition_name}", api_key, team_id, "team_matches", scan_interval, team_id=team_id))

        async_add_entities(sensors, True)

    except Exception as e:
        _LOGGER.error(f"Errore durante la configurazione dei sensori: {e}")

class CalcioLiveSensor(Entity):
    def __init__(self, hass, name, api_key, competition_code=None, sensor_type=None, scan_interval=timedelta(minutes=5), team_id=None):
        self.hass = hass
        self._name = name
        self._api_key = api_key
        self._competition_code = competition_code
        self._team_id = team_id
        self._sensor_type = sensor_type
        self._scan_interval = scan_interval
        self._state = None
        self._attributes = {}
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
        """Indica se il sensore deve essere aggiornato."""
        return True

    async def async_update(self):
        url = await self._build_url()
        headers = {"X-Auth-Token": self._api_key}

        if url is None:
            #_LOGGER.error(f"URL is None for {self._name}")
            return

        async with semaphore:  # Usa il semaforo per limitare a 50 richieste al minuto
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 429:
                            #_LOGGER.error(f"Errore HTTP 429: Rate limit superato per {self._name}")
                            self._state = None
                            await asyncio.sleep(60)  # Pausa di 1 minuto prima di ritentare
                            return
                        elif response.status != 200:
                            return
                        data = await response.json()
                        self._process_data(data)

                        self._request_count += 1
                        self._last_request_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        _LOGGER.info(f"Richiesta API {self._request_count} effettuata per {self._name} alle {self._last_request_time}")
            except aiohttp.ClientError as error:
                _LOGGER.error(f"Errore nel recupero dei dati per {self._name}: {error}")
                self._state = None

    async def _build_url(self):
        base_url = "https://api.football-data.org/v4"
        competitions_url      = f"{base_url}/competitions"
        competition_sp_url    = f"{base_url}/competitions/{self._competition_code}" #Competizioni
        standings_url         = f"{base_url}/competitions/{self._competition_code}/standings?season=2024" #Classifica
        scorers_url           = f"{base_url}/competitions/{self._competition_code}/scorers" #Capocannonieri
        match_url             = f"{base_url}/competitions/{self._competition_code}/matches?matchday=" #Match giornata campionato
        match_team_url        = f"{base_url}/teams/{self._team_id}/matches" #Match della squadra
        matchof_day_url       = f"{base_url}/matches/" #Match del giorno
        
        if self._sensor_type == "competitions":
            return competitions_url
        elif self._sensor_type == "standings":
            return standings_url
        elif self._sensor_type == "match_day":
            headers = {"X-Auth-Token": self._api_key}
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(competition_sp_url, headers=headers) as response:
                        if response.status != 200:
                            #_LOGGER.error(f"Errore HTTP {response.status} nel recuperare le standings")
                            return None

                        data = await response.json()
                        current_matchday = data.get("currentSeason", {}).get("currentMatchday")
                        
                        if current_matchday:
                            return f"{match_url}{current_matchday}"
                        else:
                            #_LOGGER.error(f"Errore: impossibile ottenere il currentMatchday dalle API")
                            return None
                except aiohttp.ClientError as error:
                    _LOGGER.error(f"Except nel recuperare le standings: {error}")
                    return None
        elif self._sensor_type == "scorers":
            return scorers_url
        elif self._sensor_type == "team_matches" and self._team_id:
            return match_team_url
        elif self._sensor_type == "matchof_day":
            return matchof_day_url
            
        return None

    def _process_data(self, data):
        if self._sensor_type == "competitions":
            count = data.get("count", 0)
            filters = data.get("filters", {})
            competitions = data.get("competitions", [])
            self._state = {f"Campionati: {count}"}
            self._attributes = {"competitions": competitions}

        elif self._sensor_type == "standings":
            filters = data.get("filters", {})
            area = data.get("area", {})
            competition = data.get("competition", {})
            season = data.get("season", {})
            standings = data.get("standings", [])
            
            campionato = data.get("competition", {}).get("name", "N/A")
            current_matchday = data.get("season", {}).get("currentMatchday", "N/A")
            
            self._state = {f"Campionato: {campionato}", f"Giornata {current_matchday}"}
            
            self._attributes = {
                "filters": filters,
                "area": area,
                "competition": competition,
                "season": season,
                "standings": standings
            }

        elif self._sensor_type == "scorers": #Capocannonieri
            count = data.get("count", 0)
            filters = data.get("filters", {})
            competition = data.get("competition", {})
            season = data.get("season", {})
            scorers = data.get("scorers", [])
            
            campionato = data.get("competition", {}).get("name", "N/A")
            stagione = data.get("filters", {}).get("season", "N/A")
            giornata = data.get("season", {}).get("currentMatchday", "N/A")
            
            self._state = {f"Campionato: {campionato}", f"Stagione: {stagione}", f"Giornata: {giornata}"}
            
            self._attributes = {
                "count": count,
                "filters": filters,
                "competition": competition,
                "season": season,
                "scorers": scorers
            }
        
        elif self._sensor_type == "match_day": #Match della giornata di campionato
           filters = data.get("filters", {})
           resultSet = data.get("resultSet", {})
           competition = data.get("competition", {})
           matches = data.get("matches", [])
           
           stagione = data.get("filters", {}).get("season", "N/A")
           giornata = data.get("filters", {}).get("matchday", "N/A")
           giocate = data.get("resultSet", {}).get("played", "N/A")
           
           self._state = {f"Stagione: {stagione}", f"Giornata: {giornata}", f"Giocate: {giocate}"}
           
           self._attributes = {
               "filters": filters,
               "resultSet": resultSet,
               "competition": competition,
               "matches": matches
           }

        elif self._sensor_type == "matchof_day": #Partite del giorno
            filters = data.get("filters", {})
            resultSet = data.get("resultSet", {})
            matches = data.get("matches", [])
            
            totale = data.get("resultSet", {}).get("count", "N/A")
            giocate = data.get("resultSet", {}).get("played", "N/A")
            
            self._state = {f"Totale: {totale}", f"Giocate: {giocate}"}
            
            self._attributes = {
                "filters": filters,
                "resultSet": resultSet,
                "matches": matches
            }

        elif self._sensor_type == "team_matches": #Partite squadra preferita
            filters = data.get("filters", {})
            resultSet = data.get("resultSet", {})
            matches = data.get("matches", [])
            
            totali = data.get("filters", {}).get("count", "N/A")
            giocate = data.get("resultSet", {}).get("played", "N/A")
            vinte = data.get("resultSet", {}).get("wins", "N/A")
            pareggiate = data.get("resultSet", {}).get("draws", "N/A")
            perse = data.get("resultSet", {}).get("losses", "N/A")
            
            self._state = {f"Totali: {totali}", f"Giocate: {giocate}", f"Vinte: {vinte}", f"Pareggiate: {pareggiate}", f"Perse: {perse}"}
            
            self._attributes = {
                "filters": filters,
                "resultSet": resultSet,
                "matches": matches
            }
