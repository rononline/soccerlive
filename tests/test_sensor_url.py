"""Sensor URL tests.

These tests import sensor.py with lightweight Home Assistant/aiohttp stubs so
URL-building regressions can be tested without a full HA test environment.
"""

import asyncio
import importlib
import logging
import sys
import types
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def _load_sensor_module():
    class _Entity:
        pass

    class _Store:
        def __init__(self, *args, **kwargs):
            pass

    class _ClientTimeout:
        def __init__(self, *args, **kwargs):
            pass

    class _ClientError(Exception):
        pass

    class _ClientResponseError(_ClientError):
        def __init__(self, status=500, message=""):
            super().__init__(message)
            self.status = status
            self.message = message

    _install_module("aiohttp", ClientTimeout=_ClientTimeout, ClientError=_ClientError, ClientResponseError=_ClientResponseError)
    _install_module("homeassistant")
    _install_module("homeassistant.config_entries", ConfigEntry=object)
    _install_module("homeassistant.core", HomeAssistant=object)
    _install_module("homeassistant.helpers")
    _install_module("homeassistant.helpers.entity", Entity=_Entity)
    _install_module("homeassistant.helpers.storage", Store=_Store)
    _install_module("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
    _install_module("homeassistant.helpers.event", async_call_later=lambda *args, **kwargs: None)
    _install_module("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda hass: None)

    return importlib.import_module("custom_components.soccer_live.sensor")


_sensor_mod = _load_sensor_module()
SoccerLiveSensor = _sensor_mod.SoccerLiveSensor


def _sensor(sensor_type, code="ned.1", team_name=None, team_id="1234"):
    sensor = SoccerLiveSensor.__new__(SoccerLiveSensor)
    sensor._name = f"test_{sensor_type}"
    sensor._code = code
    sensor._sensor_type = sensor_type
    sensor._team_name = team_name
    sensor._team_id = team_id
    sensor._start_date = datetime(2026, 1, 1)
    sensor._end_date = datetime(2026, 12, 31)
    sensor._dyn_start_date = None
    sensor._dyn_end_date = None
    sensor.base_url = "https://site.web.api.espn.com/apis/v2/sports/soccer"
    sensor.base_url_2 = "https://site.api.espn.com/apis/site/v2/sports/soccer"
    sensor.base_url_3 = "https://site.web.api.espn.com/apis/site/v2/sports/soccer"

    async def _calendar_should_not_be_called():
        raise AssertionError(f"calendar should not be called for {sensor_type}")

    sensor._get_calendar_data = _calendar_should_not_be_called
    return sensor


def test_standings_url_does_not_fetch_calendar():
    sensor = _sensor("standings", code="ned.1")

    url = asyncio.run(sensor._build_url())

    assert url == "https://site.web.api.espn.com/apis/v2/sports/soccer/ned.1/standings?"


def test_team_matches_mixed_url_does_not_fetch_calendar():
    sensor = _sensor("team_matches_mixed", code="ned.1", team_name="Feyenoord", team_id="1234")

    url = asyncio.run(sensor._build_url())

    assert url == "https://site.web.api.espn.com/apis/site/v2/sports/soccer/all/teams/1234/schedule?fixture=true"


def test_all_matches_today_url_does_not_fetch_calendar():
    sensor = _sensor("all_matches_today", code="99999")

    url = asyncio.run(sensor._build_url())

    assert url == "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"


def test_team_match_uses_calendar_dates_when_available():
    sensor = _sensor("team_match", code="ned.1")
    calls = {"count": 0}

    async def _calendar():
        calls["count"] += 1
        return "2026-08-01T00:00Z", "2027-06-01T00:00Z"

    sensor._get_calendar_data = _calendar

    url = asyncio.run(sensor._build_url())

    assert calls["count"] == 1
    assert url == "https://site.web.api.espn.com/apis/site/v2/sports/soccer/ned.1/scoreboard?limit=1000&dates=20260801-20270601"
    assert sensor._dyn_start_date == datetime(2026, 8, 1)
    assert sensor._dyn_end_date == datetime(2027, 6, 1)


def test_team_match_falls_back_to_static_dates_when_calendar_missing():
    sensor = _sensor("team_match", code="ned.1")

    async def _calendar():
        return None, None

    sensor._get_calendar_data = _calendar

    url = asyncio.run(sensor._build_url())

    assert url == "https://site.web.api.espn.com/apis/site/v2/sports/soccer/ned.1/scoreboard?limit=1000&dates=20260101-20261231"


def test_team_match_omits_dates_when_calendar_and_filters_are_missing():
    sensor = _sensor("team_match", code="ned.1")
    sensor._start_date = None
    sensor._end_date = None

    async def _calendar():
        return None, None

    sensor._get_calendar_data = _calendar

    url = asyncio.run(sensor._build_url())

    assert url == "https://site.web.api.espn.com/apis/site/v2/sports/soccer/ned.1/scoreboard?limit=1000"


def test_failed_processing_does_not_cache_response(monkeypatch):
    sensor = _sensor("team_match", code="ned.1")
    sensor._last_error = None
    sensor._last_successful_update = None
    sensor._request_count = 0
    sensor._last_request_time = None
    sensor._scorers_unavailable = False
    sensor._schedule_live_refresh = lambda: None

    async def _build_url():
        return "https://example.test/scoreboard"

    async def _process_and_apply(data):
        raise ValueError("broken payload")

    class _Response:
        status = 200

        async def read(self):
            return b'{"events": []}'

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    class _Session:
        def get(self, *args, **kwargs):
            return _Response()

    class _Hass:
        async def async_add_executor_job(self, func, *args):
            return func(*args)

    sensor.hass = _Hass()
    sensor._build_url = _build_url
    sensor._process_and_apply = _process_and_apply
    SoccerLiveSensor._cache = {}
    SoccerLiveSensor._fetch_locks = {}
    monkeypatch.setattr(_sensor_mod, "async_get_clientsession", lambda hass: _Session())

    asyncio.run(sensor.async_update())

    assert "https://example.test/scoreboard" not in SoccerLiveSensor._cache
    assert sensor._last_error == "broken payload"


def test_calendar_issue_logging_is_throttled(caplog):
    caplog.set_level(logging.DEBUG, logger="custom_components.soccer_live.sensor")
    sensor = _sensor("team_match", code="ned.1")
    _sensor_mod.SoccerLiveSensor._calendar_error_logs = {}

    sensor._log_calendar_fetch_issue("timeout", "Calendar fetch timed out for %s", sensor._name)
    sensor._log_calendar_fetch_issue("timeout", "Calendar fetch timed out for %s", sensor._name)

    warning_records = [record for record in caplog.records if record.levelname == "WARNING"]
    debug_records = [record for record in caplog.records if record.levelname == "DEBUG"]

    assert len(warning_records) == 1
    assert len(debug_records) == 1
