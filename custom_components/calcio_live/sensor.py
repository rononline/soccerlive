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
        if "calciolive_matchof_day" not in hass.data[DOMAIN] and competition_code:
            sensors.append(CalcioLiveSensor(hass, f"calciolive_matchof_day", api_key, competition_code, "matchof_day"))
            hass.data[DOMAIN]["calciolive_matchof_day"] = True
        
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
        competition_sp_url    = f"{base_url}/competitions/{self._competition_code}" #Competizioni
        standings_url         = f"{base_url}/competitions/{self._competition_code}/standings?season=2024" #Classifica
        scorers_url           = f"{base_url}/competitions/{self._competition_code}/scorers" #Capocannonieri
        match_url             = f"{base_url}/competitions/{self._competition_code}/matches?matchday=" #Match giornata campionato
        match_team_url        = f"{base_url}/teams/{self._team_id}/matches" #Match della squadra
        matchof_day_url           = f"{base_url}/matches/" #Match del giorno
        
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
            
        elif self._sensor_type == "matchof_day":
            return matchof_day_url
            
        return None

    def _process_data(self, data):
        if self._sensor_type == "competitions":
            count = data.get("count", 0)
            filters = data.get("filters", {})
            competitions = data.get("competitions", [])
            self._state = {f"Campionati: {count}"}
            
            #self._state = len(data.get("competitions", []))
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
