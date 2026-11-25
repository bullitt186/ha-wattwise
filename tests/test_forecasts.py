"""Forecast building: consumption history, Solcast and EPEX Spot attribute formats."""

import datetime
import json

import pytest
from conftest import NOW

HISTORY_DAYS = "input_number.history_days"


def at(days=0, hours=0, minutes=0):
    """ISO time stamp relative to NOW, as Home Assistant writes `last_changed`."""
    return (
        NOW + datetime.timedelta(days=days, hours=hours, minutes=minutes)
    ).isoformat()


class TestConsumptionForecast:
    """Average of the recorded consumption per 15-minute slot of the day (README, How It Works)."""

    def test_average_per_slot_of_the_history_window(self, app):
        app.states[HISTORY_DAYS] = "2"
        history = [
            {"state": "1.0", "last_changed": at(days=-1)},  # 10:00 slot
            {"state": "3.0", "last_changed": at(days=-1, minutes=5)},  # 10:00 slot
            {"state": "4.0", "last_changed": at(days=-1, minutes=15)},  # 10:15 slot
            {"state": "unavailable", "last_changed": at(days=-1, minutes=20)},
            {"state": "100.0", "last_changed": at(days=-3)},  # outside the 2 days
        ]
        with open(app.CONSUMPTION_HISTORY_FILE, "w") as f:
            json.dump(history, f)

        app.get_consumption_forecast()

        assert len(app.consumption_forecast) == app.T == 8
        assert app.consumption_forecast[0] == pytest.approx(2.0)
        assert app.consumption_forecast[1] == pytest.approx(4.0)
        assert app.consumption_forecast[2:] == [0.0] * 6

    def test_entries_older_than_the_window_are_dropped_from_the_file(self, app):
        app.states[HISTORY_DAYS] = "2"
        with open(app.CONSUMPTION_HISTORY_FILE, "w") as f:
            json.dump(
                [
                    {"state": "1.0", "last_changed": at(days=-1)},
                    {"state": "9.0", "last_changed": at(days=-3)},
                ],
                f,
            )

        app.get_consumption_forecast()

        with open(app.CONSUMPTION_HISTORY_FILE) as f:
            kept = json.load(f)
        assert [entry["state"] for entry in kept] == ["1.0"]

    def test_invalid_history_days_fall_back_to_the_app_setting(self, app):
        app.states[HISTORY_DAYS] = "unknown"
        app.args["consumption_history_days"] = 5
        app.get_consumption_forecast()
        assert app.CONSUMPTION_HISTORY_DAYS == 5


def solcast(start, values):
    """Solcast `detailedForecast` entries: 30-minute `period_start` and `pv_estimate` in kW."""
    return [
        {
            "period_start": (start + datetime.timedelta(minutes=30 * i)).isoformat(),
            "pv_estimate": value,
            "pv_estimate10": value * 0.5,
            "pv_estimate90": value * 1.5,
        }
        for i, value in enumerate(values)
    ]


class TestSolarForecast:
    """Solcast's 30-minute values interpolated linearly to 15-minute steps."""

    def set_forecast(self, app, today, tomorrow=None):
        app.states[(app.SOLAR_FORECAST_SENSOR_TODAY, "detailedForecast")] = today
        app.states[(app.SOLAR_FORECAST_SENSOR_TOMORROW, "detailedForecast")] = tomorrow

    def test_linear_interpolation_between_30_minute_points(self, app):
        self.set_forecast(app, solcast(NOW, [2.0, 3.0, 4.0, 4.0, 5.0]))
        app.get_solar_production_forecast()
        assert app.solar_forecast == pytest.approx(
            [2.0, 2.5, 3.0, 3.5, 4.0, 4.0, 4.0, 4.5]
        )

    def test_utc_time_stamps_are_converted_to_local_time(self, app):
        utc_start = NOW.astimezone(datetime.UTC)
        self.set_forecast(app, solcast(utc_start, [1.0, 1.0, 1.0, 1.0, 1.0]))
        app.get_solar_production_forecast()
        assert app.solar_forecast == pytest.approx([1.0] * 8)

    def test_horizon_is_cut_where_the_forecast_ends(self, app):
        self.set_forecast(app, solcast(NOW, [2.0, 2.0, 2.0]))  # 10:00 to 11:00
        app.get_solar_production_forecast()
        assert app.solar_forecast == pytest.approx([2.0] * 5)
        assert app.T == 5

    def test_no_forecast_for_today_is_an_error(self, app):
        self.set_forecast(app, None)
        app.get_solar_production_forecast()
        assert app.errors
        assert app.solar_forecast == []


def epex(values):
    """Entries of the `today`/`tomorrow` attributes of sensor.wattwise_energy_prices.

    wattwise.yaml builds them from the EPEX Spot integration's `data` attribute: one entry
    per 15-minute period with `total` = price_per_kwh in EUR/kWh.
    """
    return [{"total": value} for value in values]


class TestPriceForecast:
    """Prices from the current 15-minute index on, converted from EUR/kWh to ct/kWh."""

    def test_prices_start_at_the_current_step(self, app):
        today = [0.10] * 96
        today[40:48] = [
            0.20,
            0.21,
            0.22,
            0.23,
            0.24,
            0.25,
            0.26,
            0.27,
        ]  # 10:00 to 11:45
        app.states[(app.PRICE_FORECAST_SENSOR, "today")] = epex(today)
        app.get_energy_price_forecast()
        assert app.price_forecast == pytest.approx([20, 21, 22, 23, 24, 25, 26, 27])

    def test_tomorrow_continues_after_midnight(self, app):
        app.T = 60  # 10:00 today to 01:00 tomorrow
        app.states[(app.PRICE_FORECAST_SENSOR, "today")] = epex([0.10] * 96)
        app.states[(app.PRICE_FORECAST_SENSOR, "tomorrow")] = epex([0.30] * 96)
        app.get_energy_price_forecast()
        assert len(app.price_forecast) == 60
        assert app.price_forecast[55] == pytest.approx(10)  # 23:45
        assert app.price_forecast[56] == pytest.approx(30)  # 00:00 tomorrow

    def test_horizon_is_cut_where_the_prices_end(self, app):
        app.T = 60
        app.states[(app.PRICE_FORECAST_SENSOR, "today")] = epex([0.10] * 96)
        app.get_energy_price_forecast()
        assert len(app.price_forecast) == 56
        assert app.T == 56
