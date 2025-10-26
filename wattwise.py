# This file is part of WattWise.
# Origin: https://github.com/bullitt186/ha-wattwise
# Author: Bastian Stahmer
#
# WattWise is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# WattWise is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import json
import os
from datetime import timedelta

import appdaemon.plugins.hass.hassapi as hass
import numpy as np
import pulp
import tzlocal


class WattWise(hass.Hass):
    """
    WattWise is an AppDaemon application for Home Assistant that optimizes battery usage
    based on consumption forecasts, solar production forecasts, and energy price forecasts.
    It schedules charging and discharging actions to minimize energy costs and maximize
    battery efficiency.
    """

    def initialize(self):
        """
        Initializes the WattWise AppDaemon application.

        This method sets up the initial configuration, schedules the hourly optimization
        process, and listens for manual optimization triggers. It fetches initial states
        of charger and discharger switches to track current charging and discharging statuses.
        """
        # Get user-specific settings from app configuration
        self.BATTERY_CAPACITY = float(self.args.get("battery_capacity", 11.2))  # kWh
        self.BATTERY_EFFICIENCY = float(self.args.get("battery_efficiency", 0.9))
        self.CHARGE_RATE_MAX = float(self.args.get("charge_rate_max", 6))  # kW
        self.DISCHARGE_RATE_MAX = float(self.args.get("discharge_rate_max", 6))  # kW
        self.TIME_HORIZON = int(self.args.get("time_horizon", 48))  # hours
        self.FEED_IN_TARIFF = float(self.args.get("feed_in_tariff", 7))  # ct/kWh
        self.CONSUMPTION_HISTORY_DAYS = int(
            self.args.get("consumption_history_days", 7)
        )  # days
        self.LOWER_BATTERY_LIMIT = float(
            self.args.get("lower_battery_limit", 1.0)
        )  # kWh

        # Get Home Assistant Entity IDs from app configuration
        self.CONSUMPTION_SENSOR = self.args.get(
            "consumption_sensor", "sensor.s10x_house_consumption"
        )
        self.SOLAR_FORECAST_SENSOR_TODAY = self.args.get(
            "solar_forecast_sensor_today", "sensor.solcast_pv_forecast_prognose_heute"
        )
        self.SOLAR_FORECAST_SENSOR_TOMORROW = self.args.get(
            "solar_forecast_sensor_tomorrow",
            "sensor.solcast_pv_forecast_prognose_morgen",
        )
        self.BATTERY_SOC_SENSOR = self.args.get(
            "battery_soc_sensor", "sensor.s10x_state_of_charge"
        )

        # Constants for Switches - No need to touch.
        self.BATTERY_CHARGING_SWITCH = (
            "input_boolean.wattwise_battery_charging_from_grid"
        )
        self.BATTERY_DISCHARGING_SWITCH = (
            "input_boolean.wattwise_battery_discharging_enabled"
        )

        # Constants for State Tracking Binary Sensors - No need to touch.
        self.BINARY_SENSOR_CHARGING = (
            "binary_sensor.wattwise_battery_charging_from_grid"
        )
        self.BINARY_SENSOR_DISCHARGING = (
            "binary_sensor.wattwise_battery_discharging_enabled"
        )

        # Constants for Forecast Sensors - No need to touch.
        self.SENSOR_CHARGE_SOLAR = "sensor.wattwise_battery_charge_from_solar"  # kW
        self.SENSOR_CHARGE_GRID = "sensor.wattwise_battery_charge_from_grid"  # kW
        self.SENSOR_CHARGE_GRID_SESSION = (
            "sensor.wattwise_battery_charge_grid_session"  # kW
        )
        self.SENSOR_DISCHARGE = "sensor.wattwise_battery_discharge"  # kW
        self.SENSOR_GRID_EXPORT = "sensor.wattwise_grid_export"  # kW
        self.SENSOR_GRID_IMPORT = "sensor.wattwise_grid_import"  # kW
        self.SENSOR_SOC = "sensor.wattwise_state_of_charge"  # kWh
        self.SENSOR_SOC_PERCENTAGE = "sensor.wattwise_state_of_charge_percentage"  # %
        self.SENSOR_CONSUMPTION_FORECAST = "sensor.wattwise_consumption_forecast"  # kW
        self.SENSOR_SOLAR_PRODUCTION_FORECAST = (
            "sensor.wattwise_solar_production_forecast"  # kW
        )
        self.BINARY_SENSOR_FULL_CHARGE_STATUS = (
            "binary_sensor.wattwise_battery_full_charge_status"  # Binary (0/1)
        )
        self.SENSOR_MAX_POSSIBLE_DISCHARGE = (
            "sensor.wattwise_maximum_discharge_possible"  # kW
        )
        self.PRICE_FORECAST_SENSOR = "sensor.wattwise_tibber_prices"
        self.SENSOR_FORECAST_HORIZON = "sensor.wattwise_forecast_horizon"  # hours
        self.SENSOR_HISTORY_HORIZON = "sensor.wattwise_history_horizon"  # hours

        # Cheap window binary sensors
        self.BINARY_SENSOR_WITHIN_CHEAPEST_1_HOUR = (
            "binary_sensor.wattwise_within_cheapest_hour"  # hours
        )
        self.BINARY_SENSOR_WITHIN_CHEAPEST_2_HOURS = (
            "binary_sensor.wattwise_within_cheapest_2_hours"  # hours
        )
        self.BINARY_SENSOR_WITHIN_CHEAPEST_3_HOURS = (
            "binary_sensor.wattwise_within_cheapest_3_hours"  # hours
        )
        self.BINARY_SENSOR_WITHIN_CHEAPEST_4_HOURS = (
            "binary_sensor.wattwise_within_cheapest_4_hours"  # hours
        )
        self.BINARY_SENSOR_WITHIN_CHEAPEST_5_HOURS = (
            "binary_sensor.wattwise_within_cheapest_5_hours"  # hours
        )
        self.BINARY_SENSOR_WITHIN_CHEAPEST_6_HOURS = (
            "binary_sensor.wattwise_within_cheapest_6_hours"  # hours
        )
        self.BINARY_SENSOR_WITHIN_CHEAPEST_7_HOURS = (
            "binary_sensor.wattwise_within_cheapest_7_hours"  # hours
        )
        self.BINARY_SENSOR_WITHIN_CHEAPEST_8_HOURS = (
            "binary_sensor.wattwise_within_cheapest_8_hours"  # hours
        )

        # Expensive window binary sensors
        self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_1_HOUR = (
            "binary_sensor.wattwise_within_most_expensive_hour"  # hours
        )
        self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_2_HOURS = (
            "binary_sensor.wattwise_within_most_expensive_2_hours"  # hours
        )
        self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_3_HOURS = (
            "binary_sensor.wattwise_within_most_expensive_3_hours"  # hours
        )
        self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_4_HOURS = (
            "binary_sensor.wattwise_within_most_expensive_4_hours"  # hours
        )
        self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_5_HOURS = (
            "binary_sensor.wattwise_within_most_expensive_5_hours"  # hours
        )
        self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_6_HOURS = (
            "binary_sensor.wattwise_within_most_expensive_6_hours"  # hours
        )
        self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_7_HOURS = (
            "binary_sensor.wattwise_within_most_expensive_7_hours"  # hours
        )
        self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_8_HOURS = (
            "binary_sensor.wattwise_within_most_expensive_8_hours"  # hours
        )

        # maximum price threshold to exclude excessively high prices in the cheap price windows
        self.MAX_PRICE_THRESH_CT = float(
            self.args.get("max_price_threshold_ct", 80)
        )  # ct/kWh

        # Usable Time Horizon
        self.T = self.TIME_HORIZON

        # Get Home Assistant URL and token from app args
        self.ha_url = self.args.get("ha_url")
        self.token = self.args.get("token")

        if not self.ha_url or not self.token:
            self.error(
                "Home Assistant URL and token must be provided in app configuration."
            )
            return

        # Initialize state tracking variables
        self.charging_from_grid = False
        self.discharging_to_house = False

        # Initialize forecast and optimization storage
        self.consumption_forecast = []
        self.solar_forecast = []
        self.price_forecast = []
        self.charging_schedule = []
        self.max_discharge_possible = []
        self.within_cheapest_1_hour = []
        self.within_cheapest_2_hours = []
        self.within_cheapest_3_hours = []
        self.within_most_expensive_1_hour = []
        self.within_most_expensive_2_hours = []
        self.within_most_expensive_3_hours = []

        # Path to store consumption history
        self.CONSUMPTION_HISTORY_FILE = "/config/apps/wattwise_consumption_history.json"
        self.CHEAP_WINDOWS_FILE = "/config/apps/wattwise_cheap_windows.json"
        self.EXPENSIVE_WINDOWS_FILE = "/config/apps/wattwise_expensive_windows.json"

        # Fetch and set initial states from Home Assistant
        self.set_initial_states()

        # Schedule the optimization to run hourly at the top of the hour
        now = get_now_time()
        next_run = now.replace(minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += datetime.timedelta(hours=1)
        self.run_hourly(self.optimize, next_run)
        self.log(f"Scheduled hourly optimization starting at {next_run}.")

        # Listen for a custom event to trigger optimization manually
        self.listen_event(self.manual_trigger, event="MANUAL_BATTERY_OPTIMIZATION")
        self.log(
            "Listening for manual optimization trigger event 'MANUAL_BATTERY_OPTIMIZATION'."
        )
        # Run the optimization process 30 seconds after startup
        self.run_in(self.optimize, 5)
        self.log("Scheduled optimization to run 30 seconds after startup.")

    def set_initial_states(self):
        """
        Fetches and sets the initial states of the charger and discharger switches.

        This method retrieves the current state of the battery charger and discharger
        switches from Home Assistant and initializes the tracking variables
        `charging_from_grid` and `discharging_to_house` accordingly.
        """
        charger_state = self.get_state(self.BATTERY_CHARGING_SWITCH)
        discharger_state = self.get_state(self.BATTERY_DISCHARGING_SWITCH)

        if charger_state is not None:
            self.charging_from_grid = charger_state.lower() == "on"
            self.log(f"Initial charging_from_grid state: {self.charging_from_grid}")

        if discharger_state is not None:
            self.discharging_to_house = discharger_state.lower() == "on"
            self.log(f"Initial discharging_to_house state: {self.discharging_to_house}")

    def manual_trigger(self, event_name, data, kwargs):
        """
        Handles manual optimization triggers.

        This method is called when the custom event `MANUAL_BATTERY_OPTIMIZATION` is fired.
        It initiates the battery optimization process.

        Args:
            event_name (str): The name of the event.
            data (dict): The event data.
            kwargs (dict): Additional keyword arguments.
        """
        self.log("Manual optimization trigger received.")
        self.optimize({})

    def optimize(self, kwargs):
        """
        Starts the optimization process by fetching forecasts.

        Args:
            kwargs (dict): Additional keyword arguments.
        """

        self.log("############ Start Optimization ############")

        # Start fetching forecasts
        self.T = self.TIME_HORIZON  # Reset T before each run.
        self.get_consumption_forecast()
        self.get_solar_production_forecast()
        self.get_energy_price_forecast()
        self.optimize_battery()

        # Compute the maximum possible discharge per hour
        self.calculate_max_discharge_possible()

        # identify cheapest and most expensive hours based on grid tariffs
        self.identify_cheapest_hours()
        self.identify_most_expensive_hours()

        # Update forecast sensors
        self.update_forecast_sensors()

        # Schedule actions based on the optimized schedule
        # self.schedule_actions(self.charging_schedule)
        # self.log("Charging and discharging actions scheduled.")

        self.log("############ End Optimization ############")
        return

    def get_consumption_forecast(self):
        """
        Retrieves the consumption forecast for the next T hours.

        This method loads historical consumption data from a file, fetches any new data
        from Home Assistant, updates the history, and calculates the average consumption
        per hour over the past seven days.
        """
        self.log("Retrieving consumption forecast.")

        self.consumption_forecast = []

        # Load existing history
        history_data = self.load_consumption_history()

        # Determine the time window
        now = get_now_time()
        history_days_ago = now - datetime.timedelta(days=self.CONSUMPTION_HISTORY_DAYS)

        # Remove data older than 7 days
        history_data = [
            entry
            for entry in history_data
            if datetime.datetime.fromisoformat(entry["last_changed"])
            >= history_days_ago
        ]

        # Determine the last timestamp in history
        if history_data:
            last_timestamp = max(
                datetime.datetime.fromisoformat(entry["last_changed"])
                for entry in history_data
            )
        else:
            last_timestamp = history_days_ago

        # Fetch new data from last timestamp to now
        new_data = self.get_history_data(self.CONSUMPTION_SENSOR, last_timestamp, now)

        # Append new data to history
        history_data.extend(new_data)

        # Save updated history
        self.save_consumption_history(history_data)

        # Calculate average consumption per hour
        hourly_consumption = {hour: [] for hour in range(24)}
        for state in history_data:
            timestamp_str = state.get("last_changed") or state.get("last_updated")
            if timestamp_str is None:
                continue
            if isinstance(timestamp_str, str):
                timestamp = datetime.datetime.fromisoformat(timestamp_str)
            else:
                timestamp = timestamp_str
            timestamp = timestamp.astimezone(
                tzlocal.get_localzone()
            )  # Convert to local time
            hour = timestamp.hour
            value_str = state.get("state", 0)
            if is_float(value_str):
                value = float(value_str)
                hourly_consumption[hour].append(value)

        # Compute average consumption for each hour
        average_consumption = []
        for t in range(self.T):
            hour = (now + datetime.timedelta(hours=t)).hour
            values = hourly_consumption.get(hour, [])
            if values:
                avg_consumption = sum(values) / len(values)
            else:
                avg_consumption = 0  # Default if no data
            average_consumption.append(avg_consumption)

        self.log("Consumption forecast retrieved.")

        # Store the forecast for use in optimization
        self.consumption_forecast = average_consumption

    def load_consumption_history(self):
        """
        Loads the consumption history from a file.

        Returns:
            list: List of historical consumption data.
        """
        if os.path.exists(self.CONSUMPTION_HISTORY_FILE):
            try:
                with open(self.CONSUMPTION_HISTORY_FILE, "r") as f:
                    filepath = os.path.abspath(self.CONSUMPTION_HISTORY_FILE)
                    history_data = json.load(f)
                    self.log(f"Loaded existing consumption history. Path: {filepath}")
            except Exception as e:
                self.error(f"Error loading consumption history: {e}")
                history_data = []
        else:
            self.log("No existing consumption history found. Starting fresh.")
            history_data = []
        return history_data

    def save_consumption_history(self, history_data):
        """
        Saves the consumption history to a file.

        Args:
            history_data (list): List of historical consumption data.
        """
        try:
            def make_json_serializable(obj):
                if isinstance(obj, dict):
                    return {k: make_json_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_json_serializable(i) for i in obj]
                elif isinstance(obj, datetime.datetime):
                    return obj.isoformat()
                else:
                     return obj
            cleaned_data = make_json_serializable(history_data)
            
            with open(self.CONSUMPTION_HISTORY_FILE, "w") as f:
                json.dump(cleaned_data, f)
                filepath = os.path.abspath(self.CONSUMPTION_HISTORY_FILE)
                self.log(f"Consumption history saved. Path: {filepath}")
        except Exception as e:
            self.error(f"Error saving consumption history: {e}")

    def get_history_data(self, entity_id, start_time, end_time):
        """
        Retrieves historical state changes for a given entity in one-hour intervals within the specified time range.

        Args:
            entity_id (str): The entity ID for which to retrieve history.
            start_time (datetime.datetime): The start time for the history retrieval.
            end_time (datetime.datetime): The end time for the history retrieval.

        Returns:
            list of dict: A list of state change dictionaries for the entity.
        """
        history_data = []
        current_time = start_time

        while current_time < end_time:
            next_hour = current_time + datetime.timedelta(hours=1)
            # Ensure we do not go past the end_time
            if next_hour > end_time:
                next_hour = end_time

            # Convert current_time and next_hour to naive datetimes
            current_time_naive = current_time.replace(tzinfo=None)
            next_hour_naive = next_hour.replace(tzinfo=None)

            try:
                # Fetch history for the one-hour interval
                hourly_data = self.get_history(
                    entity_id=entity_id,
                    start_time=current_time_naive,
                    end_time=next_hour_naive,
                )
                if hourly_data:
                    history_data.extend(hourly_data[0])
            except Exception as e:
                self.error(
                    f"Error fetching history for {entity_id} from {current_time_naive} to {next_hour_naive}: {e}"
                )

            # Move to the next hour
            current_time = next_hour

        return history_data

    def get_solar_production_forecast(self):
        """
        Retrieves the solar production forecast for the next T hours.

        This method fetches the solar production forecast data from today's and
        tomorrow's forecast sensors in Home Assistant. It combines the data and
        maps it to the next T hours, adjusting for any forecast errors.
        """
        self.log("Retrieving solar production forecast.")
        # Retrieve solar production forecast from Home Assistant entities
        forecast_data_today = self.get_state(
            self.SOLAR_FORECAST_SENSOR_TODAY, attribute="detailedHourly"
        )
        forecast_data_tomorrow = self.get_state(
            self.SOLAR_FORECAST_SENSOR_TOMORROW, attribute="detailedHourly"
        )

        if not forecast_data_today:
            self.error("Solar production forecast data for today is unavailable.")
            return

        if not forecast_data_tomorrow:
            forecast_data_tomorrow = []
            self.log(
                "Solar production forecast data for tomorrow is not available yet."
            )

        # Combine today's and tomorrow's data
        combined_forecast_data = forecast_data_today + forecast_data_tomorrow

        self.solar_forecast = []
        now = get_now_time()
        for t in range(self.T):
            forecast_time = now + datetime.timedelta(hours=t)
            forecast_time = forecast_time.astimezone()
            value = None
            for entry in combined_forecast_data:
                entry_time = datetime.datetime.fromisoformat(entry["period_start"])
                entry_time = entry_time.astimezone()
                if (
                    entry_time.hour == forecast_time.hour
                    and entry_time.date() == forecast_time.date()
                ):
                    value = entry["pv_estimate"]
                    break
            if value is None:
                self.log(f"Solar production forecast for hour {t} not found.")
                if self.T > t:
                    self.T = t
                self.log(f"Setting time horizon to {self.T} hours.")
                break
            self.solar_forecast.append(value)
        self.log(f"Solar production forecast retrieved: {self.solar_forecast}")
        return

    def get_energy_price_forecast(self):
        """
        Retrieves the energy price forecast for the next T hours.

        This method fetches the energy price forecast data from Home Assistant's
        price forecast sensor. It combines today's and tomorrow's data and maps
        it to the next T hours, converting prices from EUR/kWh to ct/kWh.
        """
        self.log("Retrieving energy price forecast.")

        self.price_forecast = []

        # Retrieve energy price forecast from Home Assistant entity
        price_data_today = self.get_state(self.PRICE_FORECAST_SENSOR, attribute="today")
        price_data_tomorrow = self.get_state(
            self.PRICE_FORECAST_SENSOR, attribute="tomorrow"
        )

        if not price_data_today:
            self.error("Energy price forecast data for today is unavailable.")
            return

        now = get_now_time()
        current_hour = now.hour

        # Combine today's and tomorrow's data
        combined_price_data = price_data_today

        if price_data_tomorrow:
            combined_price_data += price_data_tomorrow
            self.log(
                "Tomorrow's energy price data is available and included in the forecast."
            )
        else:
            self.log("Tomorrow's energy price data is not available yet.")

        # Create the price forecast for the next T hours
        price_forecast = []
        for t in range(self.T):
            index = current_hour + t
            if index < len(combined_price_data):
                price_entry = combined_price_data[index]
                price = price_entry["total"] * 100  # Convert EUR/kWh to ct/kWh
                price_forecast.append(price)
            else:
                # If we run out of data, use the last known price
                price = combined_price_data[-1]["total"] * 100
                self.log(
                    f"Price data for hour {index} not found. Using last known price."
                )
                if self.T > t:
                    self.T = t
                self.log(f"Setting time horizon to {self.T} hours.")
                break
        self.log(f"Energy price forecast retrieved: {price_forecast}")
        self.price_forecast = price_forecast
        return

    def optimize_battery(self):
        """
        Executes the battery optimization process.

        This method retrieves the current state of charge, formulates and solves
        an optimization problem to determine the optimal charging and discharging
        schedule, updates forecast sensors, and schedules charging/discharging actions.

        Returns:
            None
        """
        self.log("Starting battery optimization process.")

        self.charging_schedule = []

        # Get initial State of Charge (SoC) in percentage
        SoC_percentage_str = self.get_state(self.BATTERY_SOC_SENSOR)
        if SoC_percentage_str is None:
            self.error(
                f"Could not retrieve state of {self.BATTERY_SOC_SENSOR}. Aborting optimization."
            )
            return

        # Convert SoC from percentage to kWh
        SoC_percentage = float(SoC_percentage_str)
        SoC_0 = (SoC_percentage / 100) * self.BATTERY_CAPACITY
        self.log(
            f"Initial SoC: {SoC_0:.2f} kWh ({SoC_percentage}% of {self.BATTERY_CAPACITY} kWh)"
        )

        # Use stored forecasts
        C_t = self.consumption_forecast
        S_t = self.solar_forecast
        P_t = self.price_forecast

        # Log the forecasts per hour for debugging
        self.log("Forecasts per hour:")
        now = get_now_time()
        for t in range(self.T):
            forecast_time = now + datetime.timedelta(hours=t)
            hour = forecast_time.hour
            self.log(
                f"Hour {hour:02d}: "
                f"Consumption = {C_t[t]:.2f} kW, "
                f"Solar = {S_t[t]:.2f} kW, "
                f"Price = {P_t[t]:.2f} ct/kWh"
            )

        # Initialize the optimization problem
        prob = pulp.LpProblem("Battery_Optimization", pulp.LpMinimize)
        self.log("Optimization problem initialized.")

        # Decision variables
        G = pulp.LpVariable.dicts("Grid_Import", (t for t in range(self.T)), lowBound=0)
        Ch_solar = pulp.LpVariable.dicts(
            "Battery_Charge_Solar", (t for t in range(self.T)), lowBound=0
        )
        Ch_grid = pulp.LpVariable.dicts(
            "Battery_Charge_Grid", (t for t in range(self.T)), lowBound=0
        )
        Dch = pulp.LpVariable.dicts(
            "Battery_Discharge", (t for t in range(self.T)), lowBound=0
        )
        SoC = pulp.LpVariable.dicts(
            "SoC",
            (t for t in range(self.T + 1)),
            lowBound=0,
            upBound=self.BATTERY_CAPACITY,
        )
        E = pulp.LpVariable.dicts("Grid_Export", (t for t in range(self.T)), lowBound=0)
        Surplus_solar = pulp.LpVariable.dicts(
            "Surplus_Solar", (t for t in range(self.T)), lowBound=0
        )
        FullCharge = pulp.LpVariable.dicts(
            "FullCharge", (t for t in range(self.T)), cat="Binary"
        )  # Binary variables
        self.log("Decision variables created.")

        # Objective function: Minimize the total cost of grid imports and grid charging, minus value of final SoC.
        # Financial value of final SoC is calculated by using the minimum forecasted price, in order to not
        # over-value the residual energy and by that reward saving energy in the battery too much.
        P_end = np.min(P_t)
        prob += (
            pulp.lpSum(
                [P_t[t] * G[t] - self.FEED_IN_TARIFF * E[t] for t in range(self.T)]
            )
            - P_end * SoC[self.T]
        )
        self.log(
            "Objective function set to minimize total cost minus value of final SoC."
        )

        # Initial SoC
        prob += SoC[0] == SoC_0
        self.log("Initial SoC constraint added.")

        M = self.BATTERY_CAPACITY * 2  # Big M value

        for t in range(self.T):
            # Energy balance with corrected battery efficiency
            prob += (
                (
                    S_t[t] + G[t] + Dch[t] * self.BATTERY_EFFICIENCY
                    == C_t[t] + Ch_solar[t] + Ch_grid[t] + E[t]
                ),
                f"Energy_Balance_{t}",
            )

            # SoC update with corrected battery efficiency
            prob += (
                SoC[t + 1]
                == SoC[t]
                + (Ch_solar[t] + Ch_grid[t]) * self.BATTERY_EFFICIENCY
                - Dch[t],
                f"SoC_Update_{t}",
            )

            # Battery capacity constraints
            prob += SoC[t + 1] >= self.LOWER_BATTERY_LIMIT, f"SoC_Min_{t}"
            prob += SoC[t + 1] <= self.BATTERY_CAPACITY, f"SoC_Max_{t}"

            # Charging limits
            prob += (
                Ch_solar[t] + Ch_grid[t] <= self.CHARGE_RATE_MAX,
                f"Charge_Rate_Limit_{t}",
            )
            prob += Ch_solar[t] <= S_t[t], f"Charge_Solar_Limit_Actual_Solar_{t}"

            # Discharging limits
            prob += Dch[t] <= self.DISCHARGE_RATE_MAX, f"Discharge_Rate_Limit_{t}"

            # Surplus solar constraints
            prob += Surplus_solar[t] >= S_t[t] - C_t[t], f"Surplus_Solar_Definition_{t}"
            prob += Surplus_solar[t] >= 0, f"Surplus_Solar_NonNegative_{t}"
            prob += Ch_solar[t] <= Surplus_solar[t], f"Solar_Charging_Limit_{t}"

            # Charging from grid cannot exceed grid import
            prob += Ch_grid[t] <= G[t], f"Grid_Charging_Limit_{t}"

            # Grid export is non-negative
            prob += E[t] >= 0, f"Grid_Export_NonNegative_{t}"

            # Linking FullCharge[t] with SoC[t+1]
            prob += (
                SoC[t + 1] >= self.BATTERY_CAPACITY - (1 - FullCharge[t]) * M,
                f"SoC_FullCharge_Link_{t}",
            )

            # Enforcing E[t] based on FullCharge[t]
            prob += E[t] <= FullCharge[t] * M, f"Export_Only_When_Full_{t}"

        self.log("Constraints added to the optimization problem.")

        # Solve the problem using a solver that supports MILP
        self.log("Starting the solver.")
        solver = pulp.GLPK_CMD(msg=1)
        prob.solve(solver)
        self.log(f"Solver status: {pulp.LpStatus[prob.status]}")

        # Check if an optimal solution was found
        if pulp.LpStatus[prob.status] != "Optimal":
            self.error("No optimal solution found for battery optimization.")
            return

        # Extract the optimized charging schedule
        now = get_now_time()
        for t in range(self.T):
            charge_solar = Ch_solar[t].varValue
            charge_grid = Ch_grid[t].varValue
            discharge = Dch[t].varValue
            export = E[t].varValue  # Grid export
            grid_import = G[t].varValue  # Grid import
            soc = SoC[t].varValue
            consumption = C_t[t]  # House consumption from forecast
            solar = S_t[t]  # Solar production from forecast
            full_charge = FullCharge[t].varValue  # FullCharge status
            forecast_time = now + datetime.timedelta(hours=t)
            hour = forecast_time.hour
            self.log(
                f"Optimized Schedule - Hour {hour:02d}: "
                f"Consumption = {consumption:.2f} kW, "
                f"Solar = {solar:.2f} kW, "
                f"Grid Import = {grid_import:.2f} kW, "
                f"Charge from Solar = {charge_solar:.2f} kW, "
                f"Charge from Grid = {charge_grid:.2f} kW, "
                f"Discharge = {discharge:.2f} kW, "
                f"Export to Grid = {export:.2f} kW, "
                f"SoC = {soc:.2f} kWh, "
                f"Battery Full = {int(full_charge)}"
            )
            self.charging_schedule.append(
                {
                    "time": forecast_time,
                    "charge_solar": charge_solar,
                    "charge_grid": charge_grid,
                    "discharge": discharge,
                    "export": export,
                    "grid_import": grid_import,
                    "consumption": consumption,
                    "soc": soc,
                    "full_charge": full_charge,
                }
            )

        return

    def identify_cheapest_hours(self):
        # Determine the forecast date (assuming price forecasts are for the next day)
        now = get_now_time()
        forecast_date = now.date()
        self.log(f"Forecast date determined as {forecast_date}.")

        # Load existing window assignments
        cheap_windows_data = self.load_cheap_windows()

        cheapest_hours_1 = []
        cheapest_hours_2 = []
        cheapest_hours_3 = []
        cheapest_hours_4 = []
        cheapest_hours_5 = []
        cheapest_hours_6 = []
        cheapest_hours_7 = []
        cheapest_hours_8 = []

        cheapest_dates_1 = []
        cheapest_dates_2 = []
        cheapest_dates_3 = []
        cheapest_dates_4 = []
        cheapest_dates_5 = []
        cheapest_dates_6 = []
        cheapest_dates_7 = []
        cheapest_dates_8 = []

        # Check if window assignments are already set for the current forecast date
        if (cheap_windows_data.get("forecast_date") != forecast_date.isoformat()) and (
            now.hour > 13
        ):
            # New forecast period, find and save new windows
            cheapest_hours_1 = self.find_cheapest_windows(self.price_forecast, 1)
            cheapest_hours_2 = self.find_cheapest_windows(self.price_forecast, 2)
            cheapest_hours_3 = self.find_cheapest_windows(self.price_forecast, 3)
            cheapest_hours_4 = self.find_cheapest_windows(self.price_forecast, 4)
            cheapest_hours_5 = self.find_cheapest_windows(self.price_forecast, 5)
            cheapest_hours_6 = self.find_cheapest_windows(self.price_forecast, 6)
            cheapest_hours_7 = self.find_cheapest_windows(self.price_forecast, 7)
            cheapest_hours_8 = self.find_cheapest_windows(self.price_forecast, 8)

            cheapest_dates_1 = [
                relativeHourToDate(hour).isoformat() for hour in cheapest_hours_1
            ]
            cheapest_dates_2 = [
                relativeHourToDate(hour).isoformat() for hour in cheapest_hours_2
            ]
            cheapest_dates_3 = [
                relativeHourToDate(hour).isoformat() for hour in cheapest_hours_3
            ]
            cheapest_dates_4 = [
                relativeHourToDate(hour).isoformat() for hour in cheapest_hours_4
            ]
            cheapest_dates_5 = [
                relativeHourToDate(hour).isoformat() for hour in cheapest_hours_5
            ]
            cheapest_dates_6 = [
                relativeHourToDate(hour).isoformat() for hour in cheapest_hours_6
            ]
            cheapest_dates_7 = [
                relativeHourToDate(hour).isoformat() for hour in cheapest_hours_7
            ]
            cheapest_dates_8 = [
                relativeHourToDate(hour).isoformat() for hour in cheapest_hours_8
            ]

            # Save windows
            windows = {
                "cheapest_dates_1": cheapest_dates_1,
                "cheapest_dates_2": cheapest_dates_2,
                "cheapest_dates_3": cheapest_dates_3,
                "cheapest_dates_4": cheapest_dates_4,
                "cheapest_dates_5": cheapest_dates_5,
                "cheapest_dates_6": cheapest_dates_6,
                "cheapest_dates_7": cheapest_dates_7,
                "cheapest_dates_8": cheapest_dates_8,
            }
            self.save_cheap_windows(forecast_date, windows)
            self.log(f"New cheap windows found for {forecast_date}: {windows}")
        else:
            # Use existing windows
            windows = cheap_windows_data.get("windows", {})
            cheapest_dates_1 = windows.get("cheapest_dates_1", [])
            cheapest_dates_2 = windows.get("cheapest_dates_2", [])
            cheapest_dates_3 = windows.get("cheapest_dates_3", [])
            cheapest_dates_4 = windows.get("cheapest_dates_4", [])
            cheapest_dates_5 = windows.get("cheapest_dates_5", [])
            cheapest_dates_6 = windows.get("cheapest_dates_6", [])
            cheapest_dates_7 = windows.get("cheapest_dates_7", [])
            cheapest_dates_8 = windows.get("cheapest_dates_8", [])

            self.log(f"Using existing cheap windows for {forecast_date}: {windows}")

            for iso_date in cheapest_dates_1:
                date = datetime.datetime.fromisoformat(iso_date)
                cheapest_hours_1.append(dateToRelativeHour(date))

            for iso_date in cheapest_dates_2:
                date = datetime.datetime.fromisoformat(iso_date)
                cheapest_hours_2.append(dateToRelativeHour(date))

            for iso_date in cheapest_dates_3:
                date = datetime.datetime.fromisoformat(iso_date)
                cheapest_hours_3.append(dateToRelativeHour(date))

            for iso_date in cheapest_dates_4:
                date = datetime.datetime.fromisoformat(iso_date)
                cheapest_hours_4.append(dateToRelativeHour(date))

            for iso_date in cheapest_dates_5:
                date = datetime.datetime.fromisoformat(iso_date)
                cheapest_hours_5.append(dateToRelativeHour(date))

            for iso_date in cheapest_dates_6:
                date = datetime.datetime.fromisoformat(iso_date)
                cheapest_hours_6.append(dateToRelativeHour(date))

            for iso_date in cheapest_dates_7:
                date = datetime.datetime.fromisoformat(iso_date)
                cheapest_hours_7.append(dateToRelativeHour(date))

            for iso_date in cheapest_dates_8:
                date = datetime.datetime.fromisoformat(iso_date)
                cheapest_hours_8.append(dateToRelativeHour(date))

        # Initialize lists to track which hours are within the cheapest and most expensive windows
        self.within_cheapest_1_hour = [False] * self.T
        self.within_cheapest_2_hours = [False] * self.T
        self.within_cheapest_3_hours = [False] * self.T
        self.within_cheapest_4_hours = [False] * self.T
        self.within_cheapest_5_hours = [False] * self.T
        self.within_cheapest_6_hours = [False] * self.T
        self.within_cheapest_7_hours = [False] * self.T
        self.within_cheapest_8_hours = [False] * self.T

        # Assign window indices to the tracking lists
        for idx in cheapest_hours_1:
            if 0 <= idx < self.T:
                self.within_cheapest_1_hour[idx] = True
        for idx in cheapest_hours_2:
            if 0 <= idx < self.T:
                self.within_cheapest_2_hours[idx] = True
        for idx in cheapest_hours_3:
            if 0 <= idx < self.T:
                self.within_cheapest_3_hours[idx] = True
        for idx in cheapest_hours_4:
            if 0 <= idx < self.T:
                self.within_cheapest_4_hours[idx] = True
        for idx in cheapest_hours_5:
            if 0 <= idx < self.T:
                self.within_cheapest_5_hours[idx] = True
        for idx in cheapest_hours_6:
            if 0 <= idx < self.T:
                self.within_cheapest_6_hours[idx] = True
        for idx in cheapest_hours_7:
            if 0 <= idx < self.T:
                self.within_cheapest_7_hours[idx] = True
        for idx in cheapest_hours_8:
            if 0 <= idx < self.T:
                self.within_cheapest_8_hours[idx] = True

        self.log(f"Cheapest 1-hour window indices: {cheapest_hours_1}")
        self.log(f"Cheapest 2-hour window indices: {cheapest_hours_2}")
        self.log(f"Cheapest 3-hour window indices: {cheapest_hours_3}")
        self.log(f"Cheapest 4-hour window indices: {cheapest_hours_4}")
        self.log(f"Cheapest 5-hour window indices: {cheapest_hours_5}")
        self.log(f"Cheapest 6-hour window indices: {cheapest_hours_6}")
        self.log(f"Cheapest 7-hour window indices: {cheapest_hours_7}")
        self.log(f"Cheapest 8-hour window indices: {cheapest_hours_8}")

        return

    def identify_most_expensive_hours(self):
        # Determine the forecast date (assuming price forecasts are for the next day)
        now = get_now_time()
        forecast_date = now.date()
        self.log(f"Forecast date determined as {forecast_date}.")

        # Load existing window assignments
        expensive_windows_data = self.load_expensive_windows()

        most_expensive_hours_1 = []
        most_expensive_hours_2 = []
        most_expensive_hours_3 = []
        most_expensive_hours_4 = []
        most_expensive_hours_5 = []
        most_expensive_hours_6 = []
        most_expensive_hours_7 = []
        most_expensive_hours_8 = []

        most_expensive_dates_1 = []
        most_expensive_dates_2 = []
        most_expensive_dates_3 = []
        most_expensive_dates_4 = []
        most_expensive_dates_5 = []
        most_expensive_dates_6 = []
        most_expensive_dates_7 = []
        most_expensive_dates_8 = []

        # Check if window assignments are already set for the current forecast date
        if (
            expensive_windows_data.get("forecast_date") != forecast_date.isoformat()
        ) and (now.hour > 13):
            # New forecast period, find and save new windows
            most_expensive_hours_1 = self.find_most_expensive_windows(
                self.price_forecast, 1
            )
            most_expensive_hours_2 = self.find_most_expensive_windows(
                self.price_forecast, 2
            )
            most_expensive_hours_3 = self.find_most_expensive_windows(
                self.price_forecast, 3
            )
            most_expensive_hours_4 = self.find_most_expensive_windows(
                self.price_forecast, 4
            )
            most_expensive_hours_5 = self.find_most_expensive_windows(
                self.price_forecast, 5
            )
            most_expensive_hours_6 = self.find_most_expensive_windows(
                self.price_forecast, 6
            )
            most_expensive_hours_7 = self.find_most_expensive_windows(
                self.price_forecast, 7
            )
            most_expensive_hours_8 = self.find_most_expensive_windows(
                self.price_forecast, 8
            )

            most_expensive_dates_1 = [
                relativeHourToDate(hour).isoformat() for hour in most_expensive_hours_1
            ]
            most_expensive_dates_2 = [
                relativeHourToDate(hour).isoformat() for hour in most_expensive_hours_2
            ]
            most_expensive_dates_3 = [
                relativeHourToDate(hour).isoformat() for hour in most_expensive_hours_3
            ]
            most_expensive_dates_4 = [
                relativeHourToDate(hour).isoformat() for hour in most_expensive_hours_4
            ]
            most_expensive_dates_5 = [
                relativeHourToDate(hour).isoformat() for hour in most_expensive_hours_5
            ]
            most_expensive_dates_6 = [
                relativeHourToDate(hour).isoformat() for hour in most_expensive_hours_6
            ]
            most_expensive_dates_7 = [
                relativeHourToDate(hour).isoformat() for hour in most_expensive_hours_7
            ]
            most_expensive_dates_8 = [
                relativeHourToDate(hour).isoformat() for hour in most_expensive_hours_8
            ]

            # Save windows
            windows = {
                "most_expensive_dates_1": most_expensive_dates_1,
                "most_expensive_dates_2": most_expensive_dates_2,
                "most_expensive_dates_3": most_expensive_dates_3,
                "most_expensive_dates_4": most_expensive_dates_4,
                "most_expensive_dates_5": most_expensive_dates_5,
                "most_expensive_dates_6": most_expensive_dates_6,
                "most_expensive_dates_7": most_expensive_dates_7,
                "most_expensive_dates_8": most_expensive_dates_8,
            }
            self.save_expensive_windows(forecast_date, windows)
            self.log(f"New expensive windows found for {forecast_date}: {windows}")
        else:
            # Use existing windows
            windows = expensive_windows_data.get("windows", {})
            most_expensive_dates_1 = windows.get("most_expensive_dates_1", [])
            most_expensive_dates_2 = windows.get("most_expensive_dates_2", [])
            most_expensive_dates_3 = windows.get("most_expensive_dates_3", [])
            most_expensive_dates_4 = windows.get("most_expensive_dates_4", [])
            most_expensive_dates_5 = windows.get("most_expensive_dates_5", [])
            most_expensive_dates_6 = windows.get("most_expensive_dates_6", [])
            most_expensive_dates_7 = windows.get("most_expensive_dates_7", [])
            most_expensive_dates_8 = windows.get("most_expensive_dates_8", [])

            self.log(f"Using existing expensive windows for {forecast_date}: {windows}")

            for iso_date in most_expensive_dates_1:
                date = datetime.datetime.fromisoformat(iso_date)
                most_expensive_hours_1.append(dateToRelativeHour(date))

            for iso_date in most_expensive_dates_2:
                date = datetime.datetime.fromisoformat(iso_date)
                most_expensive_hours_2.append(dateToRelativeHour(date))

            for iso_date in most_expensive_dates_3:
                date = datetime.datetime.fromisoformat(iso_date)
                most_expensive_hours_3.append(dateToRelativeHour(date))

            for iso_date in most_expensive_dates_4:
                date = datetime.datetime.fromisoformat(iso_date)
                most_expensive_hours_4.append(dateToRelativeHour(date))

            for iso_date in most_expensive_dates_5:
                date = datetime.datetime.fromisoformat(iso_date)
                most_expensive_hours_5.append(dateToRelativeHour(date))

            for iso_date in most_expensive_dates_6:
                date = datetime.datetime.fromisoformat(iso_date)
                most_expensive_hours_6.append(dateToRelativeHour(date))

            for iso_date in most_expensive_dates_7:
                date = datetime.datetime.fromisoformat(iso_date)
                most_expensive_hours_7.append(dateToRelativeHour(date))

            for iso_date in most_expensive_dates_8:
                date = datetime.datetime.fromisoformat(iso_date)
                most_expensive_hours_8.append(dateToRelativeHour(date))

        # Initialize lists to track which hours are within the most_expensive and most expensive windows
        self.within_most_expensive_1_hour = [False] * self.T
        self.within_most_expensive_2_hours = [False] * self.T
        self.within_most_expensive_3_hours = [False] * self.T
        self.within_most_expensive_4_hours = [False] * self.T
        self.within_most_expensive_5_hours = [False] * self.T
        self.within_most_expensive_6_hours = [False] * self.T
        self.within_most_expensive_7_hours = [False] * self.T
        self.within_most_expensive_8_hours = [False] * self.T

        # Assign window indices to the tracking lists
        for idx in most_expensive_hours_1:
            if 0 <= idx < self.T:
                self.within_most_expensive_1_hour[idx] = True
        for idx in most_expensive_hours_2:
            if 0 <= idx < self.T:
                self.within_most_expensive_2_hours[idx] = True
        for idx in most_expensive_hours_3:
            if 0 <= idx < self.T:
                self.within_most_expensive_3_hours[idx] = True
        for idx in most_expensive_hours_4:
            if 0 <= idx < self.T:
                self.within_most_expensive_4_hours[idx] = True
        for idx in most_expensive_hours_5:
            if 0 <= idx < self.T:
                self.within_most_expensive_5_hours[idx] = True
        for idx in most_expensive_hours_6:
            if 0 <= idx < self.T:
                self.within_most_expensive_6_hours[idx] = True
        for idx in most_expensive_hours_7:
            if 0 <= idx < self.T:
                self.within_most_expensive_7_hours[idx] = True
        for idx in most_expensive_hours_8:
            if 0 <= idx < self.T:
                self.within_most_expensive_8_hours[idx] = True

        self.log(f"most_expensive 1-hour window indices: {most_expensive_hours_1}")
        self.log(f"most_expensive 2-hour window indices: {most_expensive_hours_2}")
        self.log(f"most_expensive 3-hour window indices: {most_expensive_hours_3}")
        self.log(f"most_expensive 4-hour window indices: {most_expensive_hours_4}")
        self.log(f"most_expensive 5-hour window indices: {most_expensive_hours_5}")
        self.log(f"most_expensive 6-hour window indices: {most_expensive_hours_6}")
        self.log(f"most_expensive 7-hour window indices: {most_expensive_hours_7}")
        self.log(f"most_expensive 8-hour window indices: {most_expensive_hours_8}")

        return

    def schedule_actions(self, schedule):
        """
        Schedules charging and discharging actions based on the optimization schedule.

        This method iterates through the optimized charging schedule and schedules
        actions (start/stop charging, enable/disable discharging) at the appropriate times.
        It ensures that actions are only scheduled for future times and updates the
        tracking state variables to prevent redundant actions.

        Args:
            schedule (list): A list of dictionaries containing scheduling information
                             for each hour in the optimization horizon.

        Returns:
            None
        """
        self.log(
            "Scheduling charging and discharging actions based on WattWise's schedule."
        )
        now = get_now_time()

        for t, entry in enumerate(schedule):
            forecast_time = entry["time"]
            action_time = forecast_time

            # Adjust action_time to the future if the time has already passed
            if action_time < now:
                continue  # Skip scheduling actions in the past

            # Desired Charging State
            desired_charging = entry["charge_grid"] > 0

            # Desired Discharging State
            desired_discharging = entry["discharge"] > 0

            # Schedule Charging Actions
            # if desired_charging != self.charging_from_grid:
            if desired_charging:
                # Schedule start charging
                self.run_at(
                    self.start_charging,
                    action_time,
                    charge_rate=entry["charge_grid"],
                )
                self.log(
                    f"Scheduled START charging from grid at {action_time} with rate {entry['charge_grid']} kW."
                )
            else:
                # Schedule stop charging
                self.run_at(self.stop_charging, action_time)
                self.log(f"Scheduled STOP charging at {action_time}.")
            self.charging_from_grid = desired_charging  # Update the state

            # Schedule Discharging Actions
            # if desired_discharging != self.discharging_to_house:
            if desired_discharging:
                # Schedule enabling discharging
                self.run_at(self.enable_discharging, action_time)
                self.log(f"Scheduled ENABLE discharging at {action_time}.")
            else:
                # Schedule disabling discharging
                self.run_at(self.disable_discharging, action_time)
                self.log(f"Scheduled DISABLE discharging at {action_time}.")
            self.discharging_to_house = desired_discharging  # Update the state

            # Handle Exporting to Grid (Optional)
            if entry["export"] > 0:
                self.log(f"Exporting {entry['export']} kW to grid at {action_time}.")
                # Implement export actions if necessary
            # else:
            #     self.log(f"No export to grid scheduled at {action_time}.")

    def start_charging(self, kwargs):
        """
        Starts charging the battery from the grid.

        This method turns on the battery charger switch.

        Args:
            kwargs (dict): Keyword arguments containing additional parameters.
                           Expected key:
                           - charge_rate (float): The rate at which to charge the battery in kW.

        Returns:
            None
        """
        charge_rate = kwargs.get("charge_rate", self.CHARGE_RATE_MAX)
        self.log(f"Starting battery charging from grid at {charge_rate} kW.")
        # If your charger supports setting charge rate via service, implement it here.

        # Otherwise, simply turn on the charger switch
        self.call_service(
            "input_boolean/turn_on", entity_id=self.BATTERY_CHARGING_SWITCH
        )
        self.set_state(self.BINARY_SENSOR_CHARGING, state="on")

    def stop_charging(self, kwargs):
        """
        Stops charging the battery from the grid.

        This method turns off the battery charger switch.

        Args:
            kwargs (dict): Keyword arguments containing additional parameters.
                           Not used in this method.

        Returns:
            None
        """
        self.log("Stopping battery charging from grid.")
        self.call_service(
            "input_boolean/turn_off", entity_id=self.BATTERY_CHARGING_SWITCH
        )
        self.set_state(self.BINARY_SENSOR_CHARGING, state="off")

    def enable_discharging(self, kwargs):
        """
        Enables discharging of the battery to the house.

        This method turns on the battery discharger switch.

        Args:
            kwargs (dict): Keyword arguments containing additional parameters.
                           Not used in this method.

        Returns:
            None
        """
        self.log("Enabling battery discharging to the house.")
        self.call_service(
            "input_boolean/turn_on", entity_id=self.BATTERY_DISCHARGING_SWITCH
        )
        self.set_state(self.BINARY_SENSOR_DISCHARGING, state="on")

    def disable_discharging(self, kwargs):
        """
        Disables discharging of the battery to the house.

        This method turns off the battery discharger switch.

        Args:
            kwargs (dict): Keyword arguments containing additional parameters.
                           Not used in this method.

        Returns:
            None
        """
        self.log("Disabling battery discharging to the house.")
        self.call_service(
            "input_boolean/turn_off", entity_id=self.BATTERY_DISCHARGING_SWITCH
        )
        self.set_state(self.BINARY_SENSOR_DISCHARGING, state="off")

    def calculate_max_discharge_possible(self):
        """
        Calculates the maximum possible discharge per hour without increasing grid consumption,
        based on the SoC changes and discharging actions.

        Returns:
            list: A list containing the maximum possible discharge for each hour.
        """
        self.max_discharge_possible = []
        SoC_future = [entry["soc"] for entry in self.charging_schedule]
        discharge_schedule = [entry["discharge"] for entry in self.charging_schedule]
        export_schedule = [entry["export"] for entry in self.charging_schedule]
        T = len(self.charging_schedule)

        for t in range(T):
            SoC_current = SoC_future[t]
            if t < T - 1:
                SoC_next = SoC_future[t + 1]
            else:
                # For the last time step, assume SoC remains the same
                SoC_next = SoC_current

            if SoC_next > SoC_current or export_schedule[t] > 0:
                # SoC is increasing
                max_discharge = SoC_current
            else:
                # SoC is constant or decreasing
                if discharge_schedule[t] > 0:
                    max_discharge = SoC_current
                else:
                    max_discharge = 0

            # Ensure max_discharge does not exceed current SoC and discharge rate limits
            max_discharge = max(
                0, min(max_discharge, self.DISCHARGE_RATE_MAX, SoC_current)
            )

            self.max_discharge_possible.append(max_discharge)

        return self.max_discharge_possible

    @staticmethod
    def _format_forecast_value(value):
        if isinstance(value, (int, float)) and value == 0:
            return "0"
        return value

    def update_forecast_sensors(self):
        """
        Updates Home Assistant sensors with forecast data for visualization.

        This method processes the optimized charging schedule and forecast data,
        updating both regular sensors and binary sensors with the current state
        and forecast attributes. It ensures that the sensor states reflect the
        current values and that forecast data is available for visualization.

        Args:
            consumption_forecast (list of float): A list containing the consumption
                                                 forecast for each hour.
            solar_forecast (list of float): A list containing the solar production
                                            forecast for each hour.

        Returns:
            None
        """
        forecasts = {
            self.SENSOR_CHARGE_SOLAR: [],
            self.SENSOR_CHARGE_GRID: [],
            self.SENSOR_DISCHARGE: [],
            self.SENSOR_GRID_EXPORT: [],
            self.SENSOR_GRID_IMPORT: [],
            self.SENSOR_SOC: [],
            self.SENSOR_SOC_PERCENTAGE: [],
            self.SENSOR_CONSUMPTION_FORECAST: [],
            self.SENSOR_SOLAR_PRODUCTION_FORECAST: [],
            self.BINARY_SENSOR_FULL_CHARGE_STATUS: [],
            self.BINARY_SENSOR_CHARGING: [],
            self.BINARY_SENSOR_DISCHARGING: [],
            self.SENSOR_MAX_POSSIBLE_DISCHARGE: [],
            self.BINARY_SENSOR_WITHIN_CHEAPEST_1_HOUR: [],
            self.BINARY_SENSOR_WITHIN_CHEAPEST_2_HOURS: [],
            self.BINARY_SENSOR_WITHIN_CHEAPEST_3_HOURS: [],
            self.BINARY_SENSOR_WITHIN_CHEAPEST_4_HOURS: [],
            self.BINARY_SENSOR_WITHIN_CHEAPEST_5_HOURS: [],
            self.BINARY_SENSOR_WITHIN_CHEAPEST_6_HOURS: [],
            self.BINARY_SENSOR_WITHIN_CHEAPEST_7_HOURS: [],
            self.BINARY_SENSOR_WITHIN_CHEAPEST_8_HOURS: [],
            self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_1_HOUR: [],
            self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_2_HOURS: [],
            self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_3_HOURS: [],
            self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_4_HOURS: [],
            self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_5_HOURS: [],
            self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_6_HOURS: [],
            self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_7_HOURS: [],
            self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_8_HOURS: [],
        }

        self.log("Forecast Arrays initialized.")
        self.log(f"Forecast for next {len(self.charging_schedule)} hours.")
        now = get_now_time()

        # Build the forecast data
        for t, entry in enumerate(self.charging_schedule):
            forecast_time = entry["time"]
            timestamp_iso = forecast_time.isoformat()

            # Determine binary states
            desired_charging = entry["charge_grid"] > 0
            desired_discharging = entry["discharge"] > 0
            full_charge_state = entry["full_charge"] >= 1

            # Calculate SoC percentage
            soc_percentage = (entry["soc"] / self.BATTERY_CAPACITY) * 100

            # Append data to forecasts
            forecasts[self.SENSOR_CHARGE_SOLAR].append(
                [
                    timestamp_iso,
                    self._format_forecast_value(entry["charge_solar"]),
                ]
            )
            forecasts[self.SENSOR_CHARGE_GRID].append(
                [
                    timestamp_iso,
                    self._format_forecast_value(entry["charge_grid"]),
                ]
            )
            forecasts[self.SENSOR_DISCHARGE].append(
                [
                    timestamp_iso,
                    self._format_forecast_value(entry["discharge"]),
                ]
            )
            forecasts[self.SENSOR_GRID_EXPORT].append(
                [timestamp_iso, self._format_forecast_value(entry["export"])]
            )
            forecasts[self.SENSOR_GRID_IMPORT].append(
                [
                    timestamp_iso,
                    self._format_forecast_value(entry["grid_import"]),
                ]
            )
            forecasts[self.SENSOR_SOC].append(
                [timestamp_iso, self._format_forecast_value(entry["soc"])]
            )
            forecasts[self.SENSOR_SOC_PERCENTAGE].append(
                [timestamp_iso, self._format_forecast_value(soc_percentage)]
            )
            forecasts[self.BINARY_SENSOR_FULL_CHARGE_STATUS].append(
                [timestamp_iso, "on" if full_charge_state else "off"]
            )
            forecasts[self.BINARY_SENSOR_CHARGING].append(
                [timestamp_iso, "on" if desired_charging else "off"]
            )
            forecasts[self.BINARY_SENSOR_DISCHARGING].append(
                [timestamp_iso, "on" if desired_discharging else "off"]
            )
            forecasts[self.SENSOR_CONSUMPTION_FORECAST].append(
                [
                    timestamp_iso,
                    self._format_forecast_value(self.consumption_forecast[t]),
                ]
            )
            forecasts[self.SENSOR_SOLAR_PRODUCTION_FORECAST].append(
                [
                    timestamp_iso,
                    self._format_forecast_value(self.solar_forecast[t]),
                ]
            )
            self.log(f'self.solar_forecast["{t}"]: "{self.solar_forecast[t]}')
            forecasts[self.SENSOR_MAX_POSSIBLE_DISCHARGE].append(
                [
                    timestamp_iso,
                    self._format_forecast_value(self.max_discharge_possible[t]),
                ]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_CHEAPEST_1_HOUR].append(
                [timestamp_iso, "on" if self.within_cheapest_1_hour[t] else "off"]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_CHEAPEST_2_HOURS].append(
                [timestamp_iso, "on" if self.within_cheapest_2_hours[t] else "off"]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_CHEAPEST_3_HOURS].append(
                [timestamp_iso, "on" if self.within_cheapest_3_hours[t] else "off"]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_CHEAPEST_4_HOURS].append(
                [timestamp_iso, "on" if self.within_cheapest_4_hours[t] else "off"]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_CHEAPEST_5_HOURS].append(
                [timestamp_iso, "on" if self.within_cheapest_5_hours[t] else "off"]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_CHEAPEST_6_HOURS].append(
                [timestamp_iso, "on" if self.within_cheapest_6_hours[t] else "off"]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_CHEAPEST_7_HOURS].append(
                [timestamp_iso, "on" if self.within_cheapest_7_hours[t] else "off"]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_CHEAPEST_8_HOURS].append(
                [timestamp_iso, "on" if self.within_cheapest_8_hours[t] else "off"]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_1_HOUR].append(
                [timestamp_iso, "on" if self.within_most_expensive_1_hour[t] else "off"]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_2_HOURS].append(
                [
                    timestamp_iso,
                    "on" if self.within_most_expensive_2_hours[t] else "off",
                ]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_3_HOURS].append(
                [
                    timestamp_iso,
                    "on" if self.within_most_expensive_3_hours[t] else "off",
                ]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_4_HOURS].append(
                [
                    timestamp_iso,
                    "on" if self.within_most_expensive_4_hours[t] else "off",
                ]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_5_HOURS].append(
                [
                    timestamp_iso,
                    "on" if self.within_most_expensive_5_hours[t] else "off",
                ]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_6_HOURS].append(
                [
                    timestamp_iso,
                    "on" if self.within_most_expensive_6_hours[t] else "off",
                ]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_7_HOURS].append(
                [
                    timestamp_iso,
                    "on" if self.within_most_expensive_7_hours[t] else "off",
                ]
            )
            forecasts[self.BINARY_SENSOR_WITHIN_MOST_EXPENSIVE_8_HOURS].append(
                [
                    timestamp_iso,
                    "on" if self.within_most_expensive_8_hours[t] else "off",
                ]
            )

        # Update sensors
        for sensor_id, data in forecasts.items():
            # Get the current value for the sensor's state
            current_value = None
            for item in data:
                if (
                    item[0]
                    == now.replace(minute=0, second=0, microsecond=0).isoformat()
                ):
                    current_value = item[1]
                    break

            # If no current value is found, use the latest value
            if current_value is None:
                current_value = (
                    data[0][1]
                    if data
                    else ("off" if "binary_sensor" in sensor_id else "0")
                )

            self.log(f'Set state "{current_value}" for {sensor_id}.')

            # Update the sensor
            self.set_state(
                sensor_id, state=current_value, attributes={"forecast": data}
            )

        # Calculate charging session
        charge_grid_session = 0
        session_start = None
        session_duration = 0
        in_session = False

        # Get current sensor state to preserve existing session
        current_session = float(self.get_state(self.SENSOR_CHARGE_GRID_SESSION) or 0)

        if current_session > 0:
            # If there's an active session, keep it
            charge_grid_session = current_session
            in_session = True

        self.log(f"Session: current_session: {current_session}")

        # Look for a new charging session in the forecast
        for t, entry in enumerate(self.charging_schedule):
            self.log(
                f't = {t}, entry["charge_grid"] = {entry["charge_grid"]}, in_session: {in_session}'
            )
            if t == 0 and entry["charge_grid"] > 0 and not in_session:
                # Start of a new session
                in_session = True
                session_start = relativeHourToDate(t)
                charge_grid_session = entry["charge_grid"]
                session_duration = 1
            elif t == 0 and entry["charge_grid"] == 0:
                in_session = False
                session_start = None
                charge_grid_session = 0
                session_duration = 0
                break
            elif entry["charge_grid"] > 0 and in_session:
                # Continue session
                charge_grid_session += entry["charge_grid"]
                session_duration += 1
            elif entry["charge_grid"] == 0 and in_session:
                # End of session
                break

        # Update the charge grid session sensor
        self.set_state(
            self.SENSOR_CHARGE_GRID_SESSION,
            state=round(charge_grid_session, 3),
            attributes={
                "session_start": session_start.isoformat() if session_start else None,
                "session_duration": session_duration,
            },
        )
        self.log(
            f'Set state "{round(charge_grid_session, 3)}" for self.SENSOR_CHARGE_GRID_SESSION.'
        )
        self.log(
            f"Session Start: {session_start.isoformat() if session_start else None}, Session Duration: {session_duration}"
        )

        # Update the Forecast Time Horizon
        self.set_state(self.SENSOR_FORECAST_HORIZON, state=self.T)

    def find_cheapest_windows(self, prices, window_size):
        """
        Finds the start index of the cheapest consecutive window of the given size,
        ensuring no individual hour within the window exceeds the maximum price threshold.

        Args:
            prices (list of float): List of prices in ct/kWh.
            window_size (int): Size of the window in hours.

        Returns:
            list of int: List of indices that are within the cheapest window.
        """
        self.log(
            f"Finding cheapest {window_size}h window with max price threshold {self.MAX_PRICE_THRESH_CT} ct/kWh."
        )
        min_total = float("inf")
        min_start = 0
        for i in range(len(prices) - window_size + 1):
            window = prices[i : i + window_size]
            # Skip window if any hour exceeds the threshold
            if any(price > self.MAX_PRICE_THRESH_CT for price in window):
                self.log(
                    f"Skipping window {i} to {i + window_size} due to high price in window: {window}"
                )
                continue
            window_total = sum(window)
            if window_total < min_total:
                min_total = window_total
                min_start = i
        self.log(
            f"Cheapest {window_size}h window without high prices: {min_start} - {min_start + window_size}."
        )
        return list(range(min_start, min_start + window_size))

    def find_most_expensive_windows(self, prices, window_size):
        """
        Finds the start index of the most expensive consecutive window of the given size.

        Args:
            prices (list of float): List of prices in ct/kWh.
            window_size (int): Size of the window in hours.

        Returns:
            list of int: List of indices that are within the most expensive window.
        """
        self.log(f"Finding most expensive {window_size}h window.")
        max_total = float("-inf")
        max_start = 0
        for i in range(len(prices) - window_size + 1):
            window = prices[i : i + window_size]
            window_total = sum(window)
            if window_total > max_total:
                max_total = window_total
                max_start = i
        self.log(
            f"Most expensive {window_size}h window: {max_start} - {max_start + window_size}."
        )
        return list(range(max_start, max_start + window_size))

    def load_cheap_windows(self):
        """
        Loads the cheap window assignments from a JSON file.

        Returns:
            dict: Contains 'forecast_date' and 'windows' if available, else empty dict.
        """
        if os.path.exists(self.CHEAP_WINDOWS_FILE):
            try:
                with open(self.CHEAP_WINDOWS_FILE, "r") as f:
                    data = json.load(f)
                    self.log("Loaded existing cheap window assignments.")
                    return data
            except Exception as e:
                self.error(f"Error loading cheap window assignments: {e}")
                return {}
        else:
            self.log("No existing cheap window assignments found.")
            return {}

    def save_cheap_windows(self, forecast_date, windows):
        """
        Saves the cheap window assignments to a JSON file.

        Args:
            forecast_date (datetime.date): The date for which the windows are assigned.
            windows (dict): Contains lists of indices for 1, 2, and 3-hour windows.
        """
        data = {"forecast_date": forecast_date.isoformat(), "windows": windows}
        try:
            with open(self.CHEAP_WINDOWS_FILE, "w") as f:
                json.dump(data, f)
                self.log("Cheap window assignments saved.")
        except Exception as e:
            self.error(f"Error saving cheap window assignments: {e}")

    def load_expensive_windows(self):
        """
        Loads the expensive window assignments from a JSON file.

        Returns:
            dict: Contains 'forecast_date' and 'windows' if available, else empty dict.
        """
        if os.path.exists(self.EXPENSIVE_WINDOWS_FILE):
            try:
                with open(self.EXPENSIVE_WINDOWS_FILE, "r") as f:
                    data = json.load(f)
                    self.log("Loaded existing expensive window assignments.")
                    return data
            except Exception as e:
                self.error(f"Error loading expensive window assignments: {e}")
                return {}
        else:
            self.log("No existing expensive window assignments found.")
            return {}

    def save_expensive_windows(self, forecast_date, windows):
        """
        Saves the expensive window assignments to a JSON file.

        Args:
            forecast_date (datetime.date): The date for which the windows are assigned.
            windows (dict): Contains lists of indices for 1, 2, and 3-hour windows.
        """
        data = {"forecast_date": forecast_date.isoformat(), "windows": windows}
        try:
            with open(self.EXPENSIVE_WINDOWS_FILE, "w") as f:
                json.dump(data, f)
                self.log("Cheap window assignments saved.")
        except Exception as e:
            self.error(f"Error saving expensive window assignments: {e}")


def relativeHourToDate(hour: int) -> datetime.datetime:
    """
    Adds the specified number of whole hours to the current time and returns a new datetime object
    with minutes, seconds, and microseconds set to zero.

    Parameters:
    hour (int): The number of whole hours to add to the current time.

    Returns:
    datetime: The resulting datetime after adding the hours, with minutes, seconds, and microseconds set to zero.
    """
    now = get_now_time()
    new_time = now + timedelta(hours=hour)

    return new_time


def dateToRelativeHour(date: datetime.datetime) -> int:
    """
    Calculates the whole-hour offset between the given date and the current time.

    Parameters:
    date (datetime): The datetime object to compare with the current time.

    Returns:
    int: The number of whole hours difference. Positive if the date is in the future,
        negative if in the past.
    """
    now = get_now_time()
    delta = date - now
    hours = delta.total_seconds() // 3600  # Floor division to get whole hours

    return int(hours)


def get_now_time():
    now = datetime.datetime.now(tzlocal.get_localzone())
    now_hour = now.replace(minute=0, second=0, microsecond=0)
    return now_hour


def is_float(value):
    """
    Determines whether a given value can be converted to a float.

    This utility method attempts to convert the provided value to a float.
    It returns True if successful, otherwise False.

    Args:
        value (str): The value to check.

    Returns:
        bool: True if the value can be converted to float, False otherwise.
    """
    try:
        float(value)
        return True
    except ValueError:
        return False
