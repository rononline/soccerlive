import logging
import aiohttp
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    try:
        api_key = entry.data.get("api_key")
        competition_code = entry.data.get("competition_code")
        competition_name = entry.data.get("name")

        # Crea i sensori
        sensors = [
            CalcioLiveSensor(hass, f"calciolive_{competition_name}_competizioni", api_key, competition_code, "competitions"),
            CalcioLiveSensor(hass, f"calciolive_{competition_name}_classifica", api_key, competition_code, "standings"),
            CalcioLiveSensor(hass, f"calciolive_{competition_name}_match_day", api_key, competition_code, "match_day"),
            CalcioLiveSensor(hass, f"calciolive_{competition_name}_cannonieri", api_key, competition_code, "scorers")
        ]
        
        async_add_entities(sensors, True)

        return True
    except Exception as e:
        _LOGGER.error(f"Errore durante il setup dell'entry: {e}")
        return False  # Se c'è un errore, restituisci False


class CalcioLiveSensor(Entity):
    def __init__(self, hass, name, api_key, competition_code, sensor_type):
        self.hass = hass
        self._name = name
        self._api_key = api_key
        self._competition_code = competition_code
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
        url = await self._build_url()  # Usa 'await' per chiamare la funzione asincrona _build_url
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
            _LOGGER.error(f"Error fetching data for {self._name}: {error}")
            self._state = None

    async def _build_url(self):
        base_url = "https://api.football-data.org/v4/competitions"
        competitions_url = f"{base_url}/"
        competition_sp_url = f"{base_url}/{self._competition_code}"
        standings_url = f"{base_url}/{self._competition_code}/standings?season=2024"
        scorers_url = f"{base_url}/{self._competition_code}/scorers"
        match_url = f"{base_url}/{self._competition_code}/matches?matchday="

        if self._sensor_type == "competitions":
            return competitions_url

        elif self._sensor_type == "standings":
            return standings_url

        elif self._sensor_type == "match_day":
            headers = {"X-Auth-Token": self._api_key}

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(competition_sp_url, headers=headers) as response:
                        if response.status != 200:
                            _LOGGER.error(f"Errore HTTP {response.status} nel recuperare le standings")
                            return None

                        data = await response.json()

                        # Ottieni il matchday da currentSeason
                        current_matchday = data.get("currentSeason", {}).get("currentMatchday")

                        if current_matchday:
                            return f"{match_url}{current_matchday}"
                        else:
                            _LOGGER.error(f"Errore: impossibile ottenere il currentMatchday dalle API")
                            return None

            except aiohttp.ClientError as error:
                _LOGGER.error(f"Errore nel recuperare le standings: {error}")
                return None

        elif self._sensor_type == "scorers":
            return scorers_url

        return None

    def _process_data(self, data):
        if self._sensor_type == "competitions":
            self._state = len(data.get("competitions", []))
            self._attributes = {"competitions": data.get("competitions", [])}

        elif self._sensor_type == "standings":
            current_matchday = data.get("season", {}).get("currentMatchday")
            self._state = f"Giornata {current_matchday}" if current_matchday else "Giornata non disponibile"
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
