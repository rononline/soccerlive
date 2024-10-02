import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import logging
import requests
import aiohttp
from .const import DOMAIN, COMPETITIONS

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
        """Schermata per selezionare il campionato (senza richiesta API)."""
        if user_input is not None:
            competition_code = user_input.get("competition_code")
            self._data.update({"competition_code": competition_code})

            nome_sensore = COMPETITIONS.get(competition_code, competition_code)

            return self.async_create_entry(
                title=f"{COMPETITIONS[competition_code]}",
                data={
                    **self._data,
                    "competition_code": competition_code,
                    "team_id": None,
                    "name": nome_sensore,
                },
            )

        return self.async_show_form(
            step_id="campionato",
            data_schema=vol.Schema({
                vol.Required("competition_code"): vol.In(COMPETITIONS),
            }),
            errors=self._errors,
        )


    async def async_step_select_competition_for_team(self, user_input=None):
        """Schermata per selezionare il campionato per un Team (passo intermedio)."""
        if user_input is not None:
            competition_code = user_input.get("competition_code")
            self._data.update({"competition_code": competition_code})

            await self._get_teams(competition_code)
            return await self.async_step_team()

        return self.async_show_form(
            step_id="select_competition_for_team",
            data_schema=vol.Schema({
                vol.Required("competition_code"): vol.In(COMPETITIONS),
            }),
            errors=self._errors,
        )

    async def async_step_team(self, user_input=None):
        """Schermata per selezionare la squadra (dopo aver selezionato il campionato)."""
        if user_input is not None:
            if user_input["team_id"] == OPTION_MANUAL_TEAM:
                return await self.async_step_manual_team()

            team_id = user_input["team_id"]
            self._data.update({"team_id": team_id})

            nome_squadra = next((team['displayName'] for team in self._teams if team['id'] == team_id), "Nome Squadra")
            nome_squadra_normalizzato = nome_squadra.replace(" ", "_").lower()

            return self.async_create_entry(
                title=f"Team {team_id} {nome_squadra_normalizzato}",
                data={
                    **self._data,
                    "name": f"Team {team_id} {nome_squadra_normalizzato}",
                },
            )

        team_options = {team['id']: team['displayName'] for team in self._teams}
        team_options[OPTION_MANUAL_TEAM] = OPTION_MANUAL_TEAM

        return self.async_show_form(
            step_id="team",
            data_schema=vol.Schema({
                vol.Required("team_id"): vol.In(team_options),
            }),
            errors=self._errors,
        )

    async def async_step_manual_team(self, user_input=None):
        """Schermata per inserire manualmente l'ID del team."""
        if user_input is not None:
            team_id = user_input["manual_team_id"]
            nome_squadra = user_input.get("name", "Nome Squadra (a piacere)")
            nome_squadra_normalizzato = nome_squadra.replace(" ", "_").lower()

            return self.async_create_entry(
                title=f"Team {team_id} {nome_squadra_normalizzato}",
                data={
                    **self._data,
                    "team_id": team_id,
                    "name": f"Team {team_id} {nome_squadra_normalizzato}",
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

    async def _get_teams(self, competition_code):
        """Recupera la lista delle squadre dal campionato selezionato tramite API."""
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{competition_code}/teams"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    teams_data = await response.json()

                    # Estrai le squadre
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
