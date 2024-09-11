import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, CONF_API_KEY, COMPETITIONS

class CalcioLiveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestisce il flusso di configurazione per CalcioLive."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Gestisce il primo step di configurazione dell'utente."""
        errors = {}

        if user_input is not None:
            api_key = user_input["api_key"]
            competition_code = user_input.get("competition_code")
            team_id = user_input.get("team_id")

            # Assicuriamoci che venga fornito uno tra competition_code o team_id
            if not competition_code and not team_id:
                errors["base"] = "missing_required_field"
            else:
                if competition_code:
                    name_prefix = user_input.get("name", COMPETITIONS[competition_code])
                    # Creiamo i sensori relativi alla competizione
                    return self.async_create_entry(
                        title=f"{name_prefix} - {COMPETITIONS[competition_code]}",
                        data={
                            "api_key": api_key,
                            "competition_code": competition_code,
                            "team_id": None,
                            "name": name_prefix,
                        }
                    )

                if team_id:
                    name_prefix = user_input.get("name", f"Team {team_id}")
                    # Creiamo il sensore per la squadra
                    return self.async_create_entry(
                        title=f"{name_prefix} - Team {team_id}",
                        data={
                            "api_key": api_key,
                            "competition_code": None,
                            "team_id": team_id,
                            "name": name_prefix,
                        }
                    )

        # Opzioni per la selezione della competizione
        competition_options = {
            **{key: value for key, value in COMPETITIONS.items()},
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("api_key", description={"suggested_value": "Chiave API obbligatoria per football-data.org"}, default=""): str,
                vol.Optional("competition_code", description={"suggested_value": "Codice della competizione (opzionale)"}): vol.In(competition_options),
                vol.Optional("team_id", description={"suggested_value": "ID della squadra (opzionale)"}): str,
                vol.Optional("name", description={"suggested_value": "Nome del sensore"}, default="CalcioLive"): str,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Ritorna il gestore del flusso di opzioni."""
        return CalcioLiveOptionsFlowHandler(config_entry)


class CalcioLiveOptionsFlowHandler(config_entries.OptionsFlow):
    """Gestisce il flusso delle opzioni per CalcioLive."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Gestisce l'inizio del flusso di opzioni."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Mostra il form per modificare le opzioni dell'integrazione."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        competition_options = {
            **{key: value for key, value in COMPETITIONS.items()},
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("api_key", description={"suggested_value": "Chiave API obbligatoria"}, default=self.config_entry.data.get("api_key")): str,
                vol.Optional("competition_code", description={"suggested_value": "Seleziona la competizione (opzionale)"}, default=self.config_entry.data.get("competition_code")): vol.In(competition_options),
                vol.Optional("team_id", description={"suggested_value": "ID della squadra (opzionale)"}, default=self.config_entry.data.get("team_id")): str,
                vol.Optional("name", description={"suggested_value": "Nome personalizzato (opzionale)"}, default=self.config_entry.data.get("name", "CalcioLive")): str,
            }),
        )
