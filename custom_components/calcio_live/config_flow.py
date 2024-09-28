import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import logging
from .const import DOMAIN, COMPETITIONS

_LOGGER = logging.getLogger(__name__)

OPTION_SELECT_CAMPIONATO = "Campionato"
OPTION_SELECT_TEAM = "Team"

@config_entries.HANDLERS.register(DOMAIN)
class CalcioLiveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    def __init__(self):
        self._errors = {}
        self._data = {}

    async def async_step_user(self, user_input=None):
        self._errors = {}

        if user_input is not None:
            selection = user_input.get("selection")

            if selection == OPTION_SELECT_CAMPIONATO:
                self._data.update(user_input)
                return await self.async_step_campionato()

            elif selection == OPTION_SELECT_TEAM:
                self._data.update(user_input)
                return await self.async_step_team()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("selection", default=OPTION_SELECT_CAMPIONATO): vol.In([OPTION_SELECT_CAMPIONATO, OPTION_SELECT_TEAM]),
                vol.Required("api_key", description={"suggested_value": "Inserisci la tua chiave API"}): str,
            }),
            errors=self._errors,
        )

    async def async_step_campionato(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)

            nome = user_input.get("name", "Nome Campionato (a piacere)")
            nome_normalizzato = nome.replace(" ", "_").lower()

            return self.async_create_entry(
                title=f"{COMPETITIONS[user_input['competition_code']]}",
                data={
                    **self._data,
                    "competition_code": user_input["competition_code"],
                    "team_id": None,
                    "name": nome_normalizzato,
                },
            )

        return self.async_show_form(
            step_id="campionato",
            data_schema=vol.Schema({
                vol.Required("competition_code"): vol.In(COMPETITIONS),
                vol.Optional("name", default="Nome Campionato (a piacere)"): str,
            }),
            errors=self._errors,
        )

    async def async_step_team(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            team_id = user_input["team_id"]

            nome_squadra = user_input.get("name", "Nome Squadra (a piacere)")
            nome_squadra_normalizzato = nome_squadra.replace(" ", "_").lower()

            return self.async_create_entry(
                title=f"Team {team_id} {nome_squadra_normalizzato}",
                data={
                    **self._data,
                    "competition_code": None,
                    "team_id": team_id,
                    "name": f"Team {team_id} {nome_squadra_normalizzato}",
                },
            )

        return self.async_show_form(
            step_id="team",
            data_schema=vol.Schema({
                vol.Required("team_id", description={"suggested_value": "Inserisci il Team ID"}): str,
                vol.Optional("name", default="Nome Squadra (a piacere)"): str,
            }),
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CalcioLiveOptionsFlowHandler(config_entry)


class CalcioLiveOptionsFlowHandler(config_entries.OptionsFlow):

    def __init__(self, config_entry):
        self.config_entry = config_entry
        self._errors = {}

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return await self._show_options_form(user_input)

    async def _show_options_form(self, user_input):
        defaults = {
            "api_key": self.config_entry.data.get("api_key"),
            "selection": self.config_entry.data.get("selection"),
            "competition_code": self.config_entry.data.get("competition_code"),
            "team_id": self.config_entry.data.get("team_id"),
            "name": self.config_entry.data.get("name"),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional("api_key", default=defaults.get("api_key")): str,
                vol.Optional("name", default=defaults.get("name", "Nome Campionato (a piacere)")): str,
            }),
            errors=self._errors,
        )
