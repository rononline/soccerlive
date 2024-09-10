from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

DOMAIN = "calcio_live"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Calcio Live from a config entry."""
    try:
        await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

        return True
    except Exception as e:
        _LOGGER.error(f"Errore durante il setup dell'entry: {e}")
        return False

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Calcio Live component."""
    hass.data[DOMAIN] = {}
    return True
