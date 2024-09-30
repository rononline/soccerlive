import asyncio
import logging
import aiohttp
from datetime import timedelta, datetime
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import random

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    try:
        api_key = entry.data.get("api_key")
        competition_name = entry.data.get("name")
        competition_code = entry.data.get("competition_code")
        team_id = entry.data.get("team_id")

        base_scan_interval = timedelta(minutes=entry.options.get("scan_interval", 3))
        sensors = []

        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}

        if "calciolive_competizioni_created" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["calciolive_competizioni_created"] = False
        if "calciolive_matchof_day_created" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["calciolive_matchof_day_created"] = False
        if "active_competitions" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["active_competitions"] = 0

        hass.data[DOMAIN]["active_competitions"] += 1

        if not hass.data[DOMAIN]["calciolive_competizioni_created"] and competition_code:
            sensors.append(CalcioLiveSensor(
                hass, f"calciolive_competizioni".replace(" ", "_").lower(), api_key, competition_code, "competitions", base_scan_interval + timedelta(seconds=random.randint(0, 30)), config_entry_id=entry.entry_id
            ))
            hass.data[DOMAIN]["calciolive_competizioni_created"] = True

        if not hass.data[DOMAIN]["calciolive_matchof_day_created"] and competition_code:
            sensors.append(CalcioLiveSensor(
                hass, f"calciolive_matchof_day".replace(" ", "_").lower(), api_key, competition_code, "matchof_day", base_scan_interval + timedelta(seconds=random.randint(0, 30)), config_entry_id=entry.entry_id
            ))
            hass.data[DOMAIN]["calciolive_matchof_day_created"] = True

        if competition_code:
            sensors += [
                CalcioLiveSensor(
                    hass, f"calciolive_{competition_name}_classifica".replace(" ", "_").lower(), api_key, competition_code, "standings", base_scan_interval + timedelta(seconds=random.randint(0, 30)), config_entry_id=entry.entry_id
                ),
                CalcioLiveSensor(
                    hass, f"calciolive_{competition_name}_match_day".replace(" ", "_").lower(), api_key, competition_code, "match_day", base_scan_interval + timedelta(seconds=random.randint(0, 30)), config_entry_id=entry.entry_id
                ),
                CalcioLiveSensor(
                    hass, f"calciolive_{competition_name}_cannonieri".replace(" ", "_").lower(), api_key, competition_code, "scorers", base_scan_interval + timedelta(seconds=random.randint(0, 30)), config_entry_id=entry.entry_id
                )
            ]

        if team_id:
            sensors.append(CalcioLiveSensor(
                hass, f"calciolive_{competition_name}".replace(" ", "_").lower(), api_key, team_id, "team_matches", base_scan_interval + timedelta(seconds=random.randint(0, 30)), team_id=team_id, config_entry_id=entry.entry_id
            ))

        async_add_entities(sensors, True)

    except Exception as e:
        _LOGGER.error(f"Errore durante la configurazione dei sensori: {e}")

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Funzione per gestire la rimozione di una configurazione (es. rimozione di un campionato)."""
    if DOMAIN in hass.data and "active_competitions" in hass.data[DOMAIN]:
        hass.data[DOMAIN]["active_competitions"] -= 1

        if hass.data[DOMAIN]["active_competitions"] <= 0:
            hass.data[DOMAIN]["calciolive_competizioni_created"] = False
            hass.data[DOMAIN]["calciolive_matchof_day_created"] = False
            _LOGGER.info("Rimuovo sensori calciolive_competizioni e calciolive_matchof_day")

    sensors_to_remove = [
        f"calciolive_{entry.data.get('name')}_classifica",
        f"calciolive_{entry.data.get('name')}_match_day",
        f"calciolive_{entry.data.get('name')}_cannonieri",
        f"calciolive_{entry.data.get('name')}"
    ]
    for sensor in sensors_to_remove:
        entity_id = f"sensor.{sensor}"
        if entity_id in hass.states.async_entity_ids():
            await hass.states.async_remove(entity_id)

    return True


class CalcioLiveSensor(Entity):
    _cache = {}

    def __init__(self, hass, name, api_key, competition_code=None, sensor_type=None, scan_interval=timedelta(minutes=5), team_id=None, config_entry_id=None):
        self.hass = hass
        self._name = name
        self._api_key = api_key
        self._competition_code = competition_code
        self._team_id = team_id
        self._sensor_type = sensor_type
        self._scan_interval = scan_interval
        self._state = None
        self._attributes = {}
        self._config_entry_id = config_entry_id
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

    @property
    def unique_id(self):
        """Restituisce un ID unico per ogni sensore."""
        return f"{self._name}_{self._sensor_type}"

    @property
    def config_entry_id(self):
        """Associa l'entità alla config_entry."""
        return self._config_entry_id

    async def async_update(self):
        _LOGGER.info(f"Starting update for {self._name}")

        cache_key = f"{self._sensor_type}_{self._competition_code}_{self._team_id}"
        if cache_key in CalcioLiveSensor._cache and (datetime.now() - CalcioLiveSensor._cache[cache_key]["time"]).seconds < 60:
            self._process_data(CalcioLiveSensor._cache[cache_key]["data"])
            _LOGGER.info(f"Using cached data for {self._name}")
            return

        url = await self._build_url()
        headers = {"X-Auth-Token": self._api_key}

        if url is None:
            #_LOGGER.error(f"URL is None for {self._name}")
            return

        retries = 0
        while retries < 3:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            CalcioLiveSensor._cache[cache_key] = {"data": data, "time": datetime.now()}
                            self._process_data(data)
                            _LOGGER.info(f"Finished update for {self._name}")
                            break
                        elif response.status == 429:
                            #_LOGGER.error(f"Errore HTTP 429: Rate limit superato per {self._name}")
                            self._state = None
                            await asyncio.sleep(60)
                        else:
                            #_LOGGER.error(f"Errore HTTP {response.status} per {self._name}")
                            await asyncio.sleep(5)
                            retries += 1
            except aiohttp.ClientError as error:
                #_LOGGER.error(f"Errore nel recupero dei dati per {self._name}: {error}")
                await asyncio.sleep(5)
                retries += 1
            except asyncio.TimeoutError:
                #_LOGGER.error(f"Timeout raggiunto per {self._name}")
                await asyncio.sleep(5)
                retries += 1

        _LOGGER.info(f"Finished update for {self._name}")
        

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
            #matches = data.get("matches", [])
            matches = data.get("matches", [])[:25]
            
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
            #matches = data.get("matches", [])
            matches = data.get("matches", [])[:25]
            
            totali = data.get("filters", {}).get("count", "N/A")
            giocate = data.get("resultSet", {}).get("played", "N/A")
            vinte = data.get("resultSet", {}).get("wins", "N/A")
            pareggiate = data.get("resultSet", {}).get("draws", "N/A")
            perse = data.get("resultSet", {}).get("losses", "N/A")
            
            self._state = f"Totali: {totali}, Giocate: {giocate}, Vinte: {vinte}, Pareggiate: {pareggiate}, Perse: {perse}"
            self._attributes = {
                "filters": filters,
                "resultSet": resultSet,
                "matches": matches
            }
