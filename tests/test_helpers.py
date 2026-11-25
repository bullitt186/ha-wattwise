"""Price windows and the time-step helpers."""

import datetime

import pytest
from conftest import NOW

import wattwise


class TestPriceWindows:
    def test_cheapest_window_has_the_lowest_sum(self, app):
        prices = [30, 20, 10, 12, 25, 5, 40, 30]
        assert app.find_cheapest_windows(prices, 2) == [2, 3]  # 22 < 30 (5 + 25)
        assert app.find_cheapest_windows(prices, 1) == [5]

    def test_cheapest_window_skips_prices_above_the_threshold(self, app):
        app.MAX_PRICE_THRESH_CT = 35
        prices = [1, 36, 30, 30, 31, 30, 32, 33]
        # 1 + 36 is the cheapest pair, but 36 ct is above the threshold.
        assert app.find_cheapest_windows(prices, 2) == [2, 3]

    def test_most_expensive_window_has_the_highest_sum(self, app):
        prices = [30, 20, 10, 12, 25, 5, 40, 30]
        assert app.find_most_expensive_windows(prices, 2) == [6, 7]
        assert app.find_most_expensive_windows(prices, 3) == [5, 6, 7]

    @pytest.mark.parametrize("size", [0, -1, 9])
    def test_invalid_window_sizes_give_no_window(self, app, size):
        prices = [10.0] * 8
        assert app.find_cheapest_windows(prices, size) == []
        assert app.find_most_expensive_windows(prices, size) == []


class TestTimeSteps:
    def test_relative_step_to_time_and_back(self):
        later = wattwise.relativeHourToDate(6)
        assert later == NOW + datetime.timedelta(minutes=90)
        assert wattwise.dateToRelativeHour(later) == 6

    def test_partial_steps_round_down(self):
        assert wattwise.dateToRelativeHour(NOW + datetime.timedelta(minutes=29)) == 1


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1.5", True), ("-2", True), ("1e3", True), ("unavailable", False), ("", False)],
)
def test_is_float(value, expected):
    assert wattwise.is_float(value) is expected
