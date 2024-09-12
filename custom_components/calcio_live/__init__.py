import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup calcio_live from a config entry."""
    
    # Inizializza hass.data[DOMAIN] se non è già stato inizializzato
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Avvia la configurazione delle piattaforme come "sensor"
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True
