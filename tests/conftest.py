"""Test set-up: WattWise runs without AppDaemon and Home Assistant.

AppDaemon's ``hass.Hass`` base class is replaced by ``FakeHass`` before ``wattwise`` is
imported. Sensor states come from a dict, history from a list, and the clock and the time
zone are fixed, so every test runs offline and gives the same result.
"""

import datetime
import sys
import types
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

TZ = ZoneInfo("Europe/Berlin")
# A Monday at 10:00 local time, already on a 15-minute step.
NOW = datetime.datetime(2026, 3, 2, 10, 0, tzinfo=TZ)


class FakeHass:
    """The parts of AppDaemon's hass.Hass API that WattWise uses."""

    def __init__(self, args=None, states=None, history=None):
        self.args = args or {}
        self.states = states or {}
        self.history = history or []
        self.logs = []
        self.errors = []
        self.set_states = {}
        self.services = []

    def log(self, message, level="INFO"):
        self.logs.append((level, message))

    def error(self, message, level="ERROR"):
        self.errors.append(message)

    def get_state(self, entity_id, attribute=None):
        if attribute is None:
            return self.states.get(entity_id)
        return self.states.get((entity_id, attribute))

    def get_history(self, entity_id, start_time, end_time):
        return [self.history] if self.history else []

    def set_state(self, entity_id, state=None, attributes=None, **kwargs):
        self.set_states[entity_id] = {"state": state, "attributes": attributes}

    def call_service(self, service, **kwargs):
        self.services.append((service, kwargs))

    def run_every(self, callback, start, interval):
        return None

    def run_at(self, callback, start, **kwargs):
        return None

    def run_in(self, callback, delay, **kwargs):
        return None

    def listen_event(self, callback, event=None, **kwargs):
        return None

    def cancel_timer(self, handle):
        return None


hassapi = types.ModuleType("appdaemon.plugins.hass.hassapi")
hassapi.Hass = FakeHass
for name in ("appdaemon", "appdaemon.plugins", "appdaemon.plugins.hass"):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["appdaemon.plugins.hass.hassapi"] = hassapi
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wattwise  # noqa: E402

ARGS = {
    "battery_capacity_sensor": "input_number.battery_capacity",
    "battery_buffer_sensor": "input_number.battery_buffer",
    "consumption_history_days_sensor": "input_number.history_days",
    "battery_efficiency": 0.9,
    "charge_rate_max": 6,
    "discharge_rate_max": 6,
    "time_horizon": 2,
    "feed_in_tariff": 7,
    "step_minutes": 15,
    "ha_url": "http://localhost:8123",
    "token": "<test-token>",
}


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    """Freeze the clock at NOW and the local time zone at Europe/Berlin."""
    monkeypatch.setattr(wattwise, "get_now_time", lambda: NOW)
    monkeypatch.setattr(wattwise.tzlocal, "get_localzone", lambda: TZ)


@pytest.fixture
def app(tmp_path):
    """Return an initialised WattWise app with a 2-hour horizon (8 steps of 15 minutes)."""
    instance = wattwise.WattWise(args=dict(ARGS))
    instance.initialize()
    instance.CONSUMPTION_HISTORY_FILE = str(tmp_path / "history.json")
    instance.CHEAP_WINDOWS_FILE = str(tmp_path / "cheap.json")
    instance.EXPENSIVE_WINDOWS_FILE = str(tmp_path / "expensive.json")
    return instance
