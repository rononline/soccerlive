from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Soccer Live config entry."""
    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)

    sensors = []
    for entity_entry in entities:
        state = hass.states.get(entity_entry.entity_id)
        if not state:
            sensors.append({"entity_id": entity_entry.entity_id, "state": "not_loaded"})
            continue

        attrs = state.attributes
        matches = attrs.get("matches", [])
        previous = attrs.get("previous_matches", [])

        # Collect non-sensitive diagnostic info — omit large match payloads
        sensor_info: dict[str, Any] = {
            "entity_id": entity_entry.entity_id,
            "state": state.state,
            "competition_code": attrs.get("competition_code", "N/A"),
            "sensor_type": entity_entry.unique_id.split("_")[-1] if entity_entry.unique_id else "N/A",
            "request_count": attrs.get("request_count", "N/A"),
            "last_request_time": attrs.get("last_request_time", "N/A"),
            "match_count": len(matches),
            "previous_match_count": len(previous),
            "has_live_match": any(m.get("state") == "in" for m in matches),
        }

        # Cache age if available
        cache_time = None
        for entry_cache in (SoccerLiveSensor._cache or {}).values():
            if isinstance(entry_cache, dict):
                t = entry_cache.get("time")
                if t and isinstance(t, datetime):
                    age = (datetime.now() - t).total_seconds()
                    if cache_time is None or age < cache_time:
                        cache_time = age
        if cache_time is not None:
            sensor_info["cache_age_seconds"] = round(cache_time)

        sensors.append(sensor_info)

    return {
        "config_entry": {
            "competition_code": entry.data.get("competition_code", "N/A"),
            "team_name": entry.data.get("team_name", "N/A"),
            "team_id": entry.data.get("team_id", "N/A"),
            "sensor_types": entry.data.get("sensor_types", []),
            "scan_interval": entry.options.get("scan_interval", 3),
            "recent_match_hours": entry.options.get("recent_match_hours", 24),
            "notify_service": bool(entry.options.get("notify_service")),
        },
        "sensors": sensors,
    }


# Import here to avoid circular at module level
try:
    from .sensor import SoccerLiveSensor
except ImportError:
    SoccerLiveSensor = None  # type: ignore[assignment,misc]
