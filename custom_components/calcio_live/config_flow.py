import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import logging
import requests
import aiohttp
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

OPTION_SELECT_CAMPIONATO = "Campionato"
OPTION_SELECT_TEAM = "Team"
OPTION_MANUAL_TEAM = "Inserimento Manuale ID"

@config_entries.HANDLERS.register(DOMAIN)
class CalcioLiveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    def __init__(self):
        self._errors = {}
        self._data = {}
        self._teams = []

    async def async_step_user(self, user_input=None):
        """Prima schermata per selezionare Campionato o Team."""
        self._errors = {}

        if user_input is not None:
            selection = user_input.get("selection")

            if selection == OPTION_SELECT_CAMPIONATO:
                self._data.update(user_input)
                return await self.async_step_campionato()

            elif selection == OPTION_SELECT_TEAM:
                self._data.update(user_input)
                return await self.async_step_select_competition_for_team()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("selection", default=OPTION_SELECT_CAMPIONATO): vol.In([OPTION_SELECT_CAMPIONATO, OPTION_SELECT_TEAM]),
            }),
            errors=self._errors,
            description_placeholders={}
        )
    
    

    async def async_step_campionato(self, user_input=None):
        """Schermata per selezionare il campionato (recuperato tramite API, ordinato alfabeticamente e senza ricerca)."""
        if user_input is not None:
            competition_code = user_input.get("competition_code")
            competition_name = await self._get_competition_name(competition_code)  # Recupera il nome completo
            self._data.update({"competition_code": competition_code})

            return self.async_create_entry(
                title=f"{competition_name}",
                data={
                    **self._data,
                    "competition_code": competition_code,
                    "team_id": None,
                    "name": competition_name,  # Salva il nome invece del codice
                },
            )

        # Recupera e ordina le competizioni
        competitions = await self._get_competitions()
    
        # Ordinamento alfabetico per nome della competizione
        sorted_competitions = {k: v for k, v in sorted(competitions.items(), key=lambda item: item[1])}

        return self.async_show_form(
            step_id="campionato",
            data_schema=vol.Schema({
                vol.Required("competition_code"): vol.In(sorted_competitions),
            }),
            errors=self._errors,
        )

    async def _get_competitions(self):
        """Recupera e organizza le competizioni tramite API."""
        url = "https://site.api.espn.com/apis/site/v2/leagues/dropdown?lang=en&region=us&calendartype=whitelist&limit=200&sport=soccer"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    competitions_data = await response.json()

                    # Estrai le competizioni e usa il nome per il selettore
                    competitions = {
                        league['slug']: league['name']
                        for league in competitions_data.get("leagues", [])
                    }
                    _LOGGER.debug(f"Competizioni caricate: {competitions}")
                    return competitions
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Errore nel caricamento delle competizioni: {e}")
            return {}

    async def _get_competition_name(self, competition_code):
        """Recupera il nome della competizione dato il suo codice."""
        competitions = await self._get_competitions()
        return competitions.get(competition_code, "Nome Sconosciuto")
    


    async def async_step_select_competition_for_team(self, user_input=None):
        """Schermata per selezionare il campionato per un Team (passo intermedio)."""
        if user_input is not None:
            competition_code = user_input.get("competition_code")
            self._data.update({"competition_code": competition_code})

            # Recupera le squadre in modo dinamico
            await self._get_teams(competition_code)
            return await self.async_step_team()

        competitions = await self._get_competitions()
        sorted_competitions = {k: v for k, v in sorted(competitions.items(), key=lambda item: item[1])}

        return self.async_show_form(
            step_id="select_competition_for_team",
            data_schema=vol.Schema({
                vol.Required("competition_code"): vol.In(sorted_competitions),
            }),
            errors=self._errors,
        )

    async def async_step_team(self, user_input=None):
        """Schermata per selezionare la squadra (dopo aver selezionato il campionato)."""
        if user_input is not None:
            team_name = user_input["team_name"]
            competition_code = self._data.get("competition_code", "N/A")
            competition_name = await self._get_competition_name(competition_code)  # Recupera il nome della competizione
            self._data.update({"team_name": team_name})

            nome_squadra_normalizzato = team_name.replace(" ", "_").lower()

            return self.async_create_entry(
                title=f"Team {competition_name} {nome_squadra_normalizzato}",  # Nome con competizione
                data={
                    **self._data,
                    "name": f"Team {competition_name} {nome_squadra_normalizzato}",  # Salva anche nel dato
                },
            )

        # Ordina le squadre in ordine alfabetico
        team_options = {team['displayName']: team['displayName'] for team in sorted(self._teams, key=lambda t: t['displayName'])}

        return self.async_show_form(
            step_id="team",
            data_schema=vol.Schema({
                vol.Required("team_name"): vol.In(team_options),
            }),
            errors=self._errors,
        )
    
    

    async def _get_teams(self, competition_code):
        """Recupera la lista delle squadre dal campionato selezionato tramite API."""
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{competition_code}/teams"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    teams_data = await response.json()

                    # Estrai le squadre e ordinale alfabeticamente
                    self._teams = [
                        {
                            "id": team['team']['id'],
                            "displayName": team['team']['displayName']
                        }
                        for team in teams_data.get("sports", [])[0].get("leagues", [])[0].get("teams", [])
                    ]
                    _LOGGER.debug(f"Squadre caricate per {competition_code}: {self._teams}")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Errore nel caricamento delle squadre per {competition_code}: {e}")
            self._teams = []
    

    async def async_step_manual_team(self, user_input=None):
        """Schermata per inserire manualmente l'ID del team."""
        if user_input is not None:
            team_id = user_input["manual_team_id"]
            competition_code = self._data.get("competition_code", "N/A")
            competition_name = await self._get_competition_name(competition_code)  # Recupera il nome della competizione
            nome_squadra = user_input.get("name", "Nome Squadra (a piacere)")
            nome_squadra_normalizzato = nome_squadra.replace(" ", "_").lower()

            return self.async_create_entry(
                title=f"Team {competition_name} {team_id} {nome_squadra_normalizzato}",  # Nome con competizione
                data={
                    **self._data,
                    "team_id": team_id,
                    "name": f"Team {competition_name} {team_id} {nome_squadra_normalizzato}",  # Salva anche nel dato
                },
            )

        return self.async_show_form(
            step_id="manual_team",
            data_schema=vol.Schema({
                vol.Required("manual_team_id", description={"suggested_value": "Inserisci l'ID del Team manualmente"}): str,
                vol.Optional("name", default="Nome Squadra (a piacere)"): str,
            }),
            errors=self._errors,
        )
    
