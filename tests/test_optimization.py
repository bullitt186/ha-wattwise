"""The battery optimisation: constraints of the linear program and the cost model.

The model is the one in the README (How It Works) and in optimize_battery(): per step the
power balance solar + grid import + discharge * efficiency = consumption + charging + export
holds, the state of charge (SoC) moves by charging * efficiency - discharge (times the step
length) and stays between the buffer and the capacity, charge and discharge stay below their
rate limits, and the cost is the grid import at the forecast price minus the feed-in tariff
for the export minus the final SoC valued at the mean price.
"""

import pulp
import pytest

import wattwise

CAPACITY = 10.0  # kWh
BUFFER = 1.0  # kWh
EFFICIENCY = 0.9
RATE_MAX = 6.0  # kW
DELTA = 0.25  # h per 15-minute step
TOL = 1e-6


@pytest.fixture(autouse=True)
def cbc_solver(monkeypatch):
    """Use the system `cbc` like the add-on (coinor-cbc), else the one bundled with pulp."""
    system = pulp.COIN_CMD
    solver = system if system(msg=0).available() else pulp.PULP_CBC_CMD
    monkeypatch.setattr(wattwise.pulp, "COIN_CMD", lambda msg=1: solver(msg=0))


def plan(app, consumption, solar, prices, soc_percent=50.0):
    app.states["input_number.battery_capacity"] = str(CAPACITY)
    app.states["input_number.battery_buffer"] = str(BUFFER)
    app.states[app.BATTERY_SOC_SENSOR] = str(soc_percent)
    app.consumption_forecast = consumption
    app.solar_forecast = solar
    app.price_forecast = prices
    app.T = len(prices)
    app.optimize_battery()
    assert not app.errors, app.errors
    assert len(app.charging_schedule) == app.T
    return app.charging_schedule


def assert_constraints(schedule, consumption, solar):
    for t, step in enumerate(schedule):
        charge = step["charge_solar"] + step["charge_grid"]
        assert BUFFER - TOL <= step["soc"] <= CAPACITY + TOL
        assert charge <= RATE_MAX + TOL
        assert step["discharge"] <= RATE_MAX + TOL
        assert step["charge_solar"] <= solar[t] + TOL
        assert step["charge_grid"] <= step["grid_import"] + TOL
        supply = solar[t] + step["grid_import"] + step["discharge"] * EFFICIENCY
        demand = consumption[t] + charge + step["export"]
        assert supply == pytest.approx(demand, abs=TOL)
    for before, after in zip(schedule, schedule[1:], strict=False):
        moved = (
            before["charge_solar"] + before["charge_grid"]
        ) * EFFICIENCY * DELTA - before["discharge"] * DELTA
        assert after["soc"] == pytest.approx(before["soc"] + moved, abs=TOL)


def test_the_plan_starts_at_the_measured_soc(app):
    schedule = plan(app, [1.0] * 8, [0.0] * 8, [30.0] * 8, soc_percent=40.0)
    assert schedule[0]["soc"] == pytest.approx(0.4 * CAPACITY)


def test_cheap_then_expensive_prices(app):
    consumption, solar = [1.0] * 8, [0.0] * 8
    prices = [10.0] * 4 + [50.0] * 4  # mean 30 ct/kWh values the final SoC
    schedule = plan(app, consumption, solar, prices)
    assert_constraints(schedule, consumption, solar)

    # 1 kWh from the grid at 10 ct stores 0.9 kWh worth 27 ct: charge in the cheap hour,
    # at the rate limit until the battery is full.
    assert sum(step["charge_grid"] for step in schedule[:4]) > 0
    assert schedule[0]["charge_grid"] == pytest.approx(RATE_MAX)
    # 1 kWh of demand from the battery costs 1/0.9 kWh worth 33 ct, less than 50 ct from the
    # grid: the expensive hour runs on the battery.
    assert all(
        step["grid_import"] == pytest.approx(0, abs=TOL) for step in schedule[4:]
    )
    assert all(
        step["discharge"] * EFFICIENCY == pytest.approx(1.0) for step in schedule[4:]
    )


def test_export_only_with_a_full_battery(app):
    consumption = [0.5] * 8
    solar = [8.0] * 8  # more than consumption plus the charge rate limit
    schedule = plan(app, consumption, solar, [30.0] * 8, soc_percent=90.0)
    assert_constraints(schedule, consumption, solar)
    exporting = [t for t, step in enumerate(schedule) if step["export"] > TOL]
    assert exporting, "the surplus beyond the charge rate has to go to the grid"
    for t in exporting:
        assert schedule[t]["full_charge"] == pytest.approx(1)
        if t + 1 < len(schedule):  # the SoC after step t is the next step's start SoC
            assert schedule[t + 1]["soc"] == pytest.approx(CAPACITY, abs=TOL)


def test_soc_stays_above_the_buffer(app):
    consumption, solar = [4.0] * 8, [0.0] * 8
    schedule = plan(app, consumption, solar, [60.0] * 8, soc_percent=20.0)
    assert_constraints(schedule, consumption, solar)
    assert min(step["soc"] for step in schedule) >= BUFFER - TOL


def test_empty_price_forecast_aborts(app):
    app.states["input_number.battery_capacity"] = str(CAPACITY)
    app.states["input_number.battery_buffer"] = str(BUFFER)
    app.states[app.BATTERY_SOC_SENSOR] = "50"
    app.consumption_forecast, app.solar_forecast, app.price_forecast = [], [], []
    app.T = 0
    app.optimize_battery()
    assert app.errors
    assert app.charging_schedule == []
