import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, CONF_API_KEY, CONF_COMPETITION_CODE, SENSOR_TYPES

# Lista aggiornata delle competizioni estratte
COMPETITIONS = {
    "BSA": "Campeonato Brasileiro Série A",
    "ELC": "Championship",
    "PL": "Premier League",
    "CL": "UEFA Champions League",
    "EC": "European Championship",
    "FL1": "Ligue 1",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "DED": "Eredivisie",
    "PPL": "Primeira Liga",
    "CLI": "Copa Libertadores",
    "PD": "Primera Division",
    "WC": "FIFA World Cup"
}

class CalcioLiveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestisce il flusso di configurazione per CalcioLive."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Gestisce il primo step di configurazione dell'utente."""
        errors = {}

        if user_input is not None:
            api_key = user_input["api_key"]
            competition_code = user_input["competition_code"]
            name_prefix = user_input.get("name", COMPETITIONS[competition_code])

            competition_name = name_prefix.replace(" ", "").lower()

            # Creazione della configurazione
            return self.async_create_entry(
                title=f"{name_prefix} - {COMPETITIONS[competition_code]}",
                data={
                    "api_key": api_key,
                    "competition_code": competition_code,
                    "name": competition_name
                }
            )

        # Opzioni di competizione con la possibilità di personalizzare
        competition_options = {
            **{key: value for key, value in COMPETITIONS.items()},
            "XXX": "Personalizzato: Inserisci manualmente il codice della competizione"
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("api_key", description={"suggested_value": "Chiave API obbligatoria per football-data.org"}, default=""): str,
                vol.Required("competition_code", default="SA"): vol.In(competition_options),
                vol.Optional("name", description={"suggested_value": "Nome sensore"}, default="Serie A"): str,
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
            "XXX": "Personalizzato: Inserisci manualmente il codice della competizione"
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("api_key", description={"suggested_value": "Chiave API obbligatoria"}, default=self.config_entry.data.get("api_key")): str,
                vol.Required("competition_code", description={"suggested_value": "Seleziona la competizione"}, default=self.config_entry.data.get("competition_code")): vol.In(competition_options),
                vol.Optional("name", description={"suggested_value": "Nome personalizzato (opzionale)"}, default=self.config_entry.data.get("name", "Serie A")): str,
            }),
        )
