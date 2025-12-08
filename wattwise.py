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
        self.battery_capacity_sensor = self.args.get("battery_capacity_sensor")
        self.battery_buffer_sensor = self.args.get("battery_buffer_sensor")
        self.consumption_history_days_sensor = self.args.get("consumption_history_days_sensor")
        #self.BATTERY_CAPACITY = float(self.get_state(self.args["battery_capacity_sensor"])) -> pushed to optimize_battery
        #self.LOWER_BATTERY_LIMIT = float(self.get_state(self.args["battery_buffer_sensor"])) -> pushed to optimize_battery
        self.BATTERY_EFFICIENCY = float(self.args.get("battery_efficiency", 0.9))
        self.CHARGE_RATE_MAX = float(self.args.get("charge_rate_max", 6))  # kW
        self.DISCHARGE_RATE_MAX = float(self.args.get("discharge_rate_max", 6))  # kW
        self.TIME_HORIZON = int(self.args.get("time_horizon", 48))  # hours
        self.FEED_IN_TARIFF = float(self.args.get("feed_in_tariff", 7))  # ct/kWh

        # new: step size in minutes and delta in hours
        self.STEP_MINUTES = int(self.args.get("step_minutes", 15))  # minutes per timestep
        self.DELTA_HOURS = self.STEP_MINUTES / 60.0  # hours per timestep

        # Usable Time Horizon: number of timesteps (15-min steps)
        self.T = int(self.TIME_HORIZON * 60 / self.STEP_MINUTES)

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
        self.SOLAR_FORECAST_SENSOR_DAY_AFTER_TOMORROW = self.args.get(
            "solar_forecast_sensor_day_after_tomorrow",
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
        # renamed price forecast sensor entity
        self.PRICE_FORECAST_SENSOR = "sensor.wattwise_energy_prices"
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
        #self.T = self.TIME_HORIZON

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

        # Schedule the optimization to run on STEP_MINUTES interval aligned to next quarter
        now = get_now_time()
        next_run = now  # get_now_time already rounded to STEP_MINUTES
        # run_every requires start and interval in seconds
        self.run_every(self.optimize, next_run, self.STEP_MINUTES * 60)
        self.log(f"Scheduled optimization every {self.STEP_MINUTES} minutes starting at {next_run}.")

        # Listen for a custom event to trigger optimization manually
        self.listen_event(self.manual_trigger, event="MANUAL_BATTERY_OPTIMIZATION")
        self.log(
            "Listening for manual optimization trigger event 'MANUAL_BATTERY_OPTIMIZATION'."
        )
        # Run the optimization process shortly after startup
        self.run_in(self.optimize, 5)
        self.log("Scheduled optimization to run 5 seconds after startup.")

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

        # Reset T (timesteps) before each run to allow dynamic truncation in forecasts
        self.T = int(self.TIME_HORIZON * 60 / self.STEP_MINUTES)

        # Start fetching forecasts
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
        
        # Dynamisch aktuellen Wert für Verbrauchshistorie abrufen
        days_str = self.get_state(self.consumption_history_days_sensor)
        try:
            self.CONSUMPTION_HISTORY_DAYS = int(float(days_str))
        except (TypeError, ValueError):
            self.log(f"Invalid value for consumption history days: '{days_str}', using fallback", level="WARNING")
            self.CONSUMPTION_HISTORY_DAYS = int(self.args.get("consumption_history_days", 3))

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

        # Calculate average consumption per 15-min slot (96 slots)
        slots_per_day = int(24 * 60 / self.STEP_MINUTES)
        slot_consumption = {slot: [] for slot in range(slots_per_day)}

        for state in history_data:
            timestamp_str = state.get("last_changed") or state.get("last_updated")
            if timestamp_str is None:
                continue
            if isinstance(timestamp_str, str):
                timestamp = datetime.datetime.fromisoformat(timestamp_str)
            else:
                timestamp = timestamp_str
            timestamp = timestamp.astimezone(tzlocal.get_localzone())
            slot = timestamp.hour * (60 // self.STEP_MINUTES) + (timestamp.minute // self.STEP_MINUTES)
            value_str = state.get("state", 0)
            if is_float(value_str):
                value = float(value_str)
                slot_consumption[slot].append(value)

        # compute average per slot
        average_slot = []
        for slot in range(slots_per_day):
            values = slot_consumption.get(slot, [])
            if values:
                average_slot.append(sum(values) / len(values))
            else:
                average_slot.append(0.0)

        # build forecast for next T timesteps
        self.consumption_forecast = []
        for t in range(self.T):
            forecast_time = now + datetime.timedelta(minutes=self.STEP_MINUTES * t)
            slot = forecast_time.hour * (60 // self.STEP_MINUTES) + (forecast_time.minute // self.STEP_MINUTES)
            self.consumption_forecast.append(average_slot[slot])

        self.log("Consumption forecast retrieved (15-min resolution).")

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

        # use STEP_MINUTES intervals instead of 1 hour
        while current_time < end_time:
            next_time = current_time + datetime.timedelta(minutes=self.STEP_MINUTES)
            if next_time > end_time:
                next_time = end_time

            current_time_naive = current_time.replace(tzinfo=None)
            next_time_naive = next_time.replace(tzinfo=None)

            try:
                # Fetch history for the STEP_MINUTES interval
                interval_data = self.get_history(
                    entity_id=entity_id,
                    start_time=current_time_naive,
                    end_time=next_time_naive,
                )
                if interval_data:
                    history_data.extend(interval_data[0])
            except Exception as e:
                self.error(
                    f"Error fetching history for {entity_id} from {current_time_naive} to {next_time_naive}: {e}"
                )

            current_time = next_time

        return history_data

    def get_solar_production_forecast(self):
        """
        Retrieves the solar production forecast for the next T timesteps (STEP_MINUTES).
        Uses attribute "detailedForecast" from sensor and linearly interpolates 30min -> STEP_MINUTES.
        """
        self.log("Retrieving solar production forecast (interpolated to step resolution).")

        # Retrieve solar production forecast from Home Assistant entities
        forecast_data_today = self.get_state(
            self.SOLAR_FORECAST_SENSOR_TODAY, attribute="detailedForecast"
        )
        forecast_data_tomorrow = self.get_state(
            self.SOLAR_FORECAST_SENSOR_TOMORROW, attribute="detailedForecast"
        )
        forecast_data_day_after = self.get_state(
            self.SOLAR_FORECAST_SENSOR_DAY_AFTER_TOMORROW, attribute="detailedForecast"
        )

        if not forecast_data_today:
            self.error("Solar production forecast data for today is unavailable.")
            return

        if not forecast_data_tomorrow:
            forecast_data_tomorrow = []
            self.log("Solar production forecast data for tomorrow is not available yet.")
        if not forecast_data_day_after:
            forecast_data_day_after = []
            self.log("Solar production forecast data for day-after-tomorrow is not available yet.")

        # Combine and normalize forecast entries into (timestamp, value) list
        combined_forecast_data = forecast_data_today + forecast_data_tomorrow + forecast_data_day_after

        # Convert entries to sorted list of (datetime, pv_estimate)
        points = []
        for entry in combined_forecast_data:
            # expect entry["period_start"] and entry["pv_estimate"]
            try:
                t = datetime.datetime.fromisoformat(entry["period_start"])
                if t.tzinfo is None:
                    t = t.replace(tzinfo=tzlocal.get_localzone())
                else:
                    t = t.astimezone(tzlocal.get_localzone())
                v = entry.get("pv_estimate", None)
                if v is None:
                    continue
                points.append((t, float(v)))
            except Exception:
                continue
        points.sort(key=lambda x: x[0])

        if not points:
            self.error("No usable solar forecast points found.")
            return

        # Helper to interpolate linearly between the two surrounding 30-min points
        def interp_value(ts):
            # ts: timezone-aware datetime
            # if exact match
            for (t0, v0) in points:
                if t0 == ts:
                    return v0
            # find left and right points
            if ts < points[0][0] or ts > points[-1][0]:
                return None
            left = None
            right = None
            for i in range(len(points) - 1):
                if points[i][0] <= ts <= points[i + 1][0]:
                    left = points[i]
                    right = points[i + 1]
                    break
            if left is None or right is None:
                return None
            t0, v0 = left
            t1, v1 = right
            total = (t1 - t0).total_seconds()
            if total == 0:
                return v0
            weight = (ts - t0).total_seconds() / total
            return v0 + weight * (v1 - v0)

        # Build solar_forecast for next T timesteps
        self.solar_forecast = []
        now = get_now_time()
        for t in range(self.T):
            forecast_time = (now + datetime.timedelta(minutes=self.STEP_MINUTES * t)).astimezone(tzlocal.get_localzone())
            value = interp_value(forecast_time)
            if value is None:
                # if outside available range, truncate horizon
                self.log(f"Solar forecast missing for {forecast_time.isoformat()}, truncating horizon at step {t}.")
                self.T = t
                break
            self.solar_forecast.append(value)

        self.log(f"Solar production forecast retrieved (mapped to {self.STEP_MINUTES}-min): {self.solar_forecast}")
        return

    def get_energy_price_forecast(self):
        """
        Retrieves the energy price forecast for the next T timesteps (STEP_MINUTES resolution).

        Notes:
        - Expects the configured price sensor to provide lists ('today','tomorrow','day_after_tomorrow')
          where each entry corresponds to a period of length STEP_MINUTES (e.g. 15min -> 96 entries/day).
        - The function builds a forecast starting at the current STEP-aligned index.
        """
        self.log("Retrieving energy price forecast (step resolution).")

        self.price_forecast = []

        # Retrieve energy price forecast lists (assumed STEP_MINUTES resolution entries)
        price_data_today = self.get_state(self.PRICE_FORECAST_SENSOR, attribute="today")
        price_data_tomorrow = self.get_state(self.PRICE_FORECAST_SENSOR, attribute="tomorrow")
        price_data_day_after = self.get_state(self.PRICE_FORECAST_SENSOR, attribute="day_after_tomorrow")

        if not price_data_today:
            self.error("Energy price forecast data for today is unavailable.")
            return

        # Combine lists
        combined_price_data = list(price_data_today or [])
        if price_data_tomorrow:
            combined_price_data += price_data_tomorrow
        if price_data_day_after:
            combined_price_data += price_data_day_after

        # Sanity: expected entries per day given STEP_MINUTES
        slots_per_day = int(24 * 60 / self.STEP_MINUTES)
        self.log(f"Expected {slots_per_day} price slots per day (STEP_MINUTES={self.STEP_MINUTES}). Combined price points: {len(combined_price_data)}")

        # compute current index in steps (0..)
        now = get_now_time()
        current_index = now.hour * (60 // self.STEP_MINUTES) + (now.minute // self.STEP_MINUTES)

        price_forecast = []
        for t in range(self.T):
            index = current_index + t
            if index < len(combined_price_data):
                price_entry = combined_price_data[index]
                # price_entry expected to have "total"
                price = price_entry["total"] * 100  # EUR/kWh -> ct/kWh
                price_forecast.append(price)
            else:
                self.log(f"Price data for index {index} not found (combined length {len(combined_price_data)}). Truncating horizon at step {t}.")
                if self.T > t:
                    self.T = t
                break

        self.price_forecast = price_forecast
        self.log(f"Energy price forecast retrieved (steps: {len(self.price_forecast)}).")
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
        
        battery_capacity_str = self.get_state(self.args["battery_capacity_sensor"])
        buffer_limit_str = self.get_state(self.args["battery_buffer_sensor"])
        
        try:
            battery_capacity = float(battery_capacity_str)
            buffer_limit = float(buffer_limit_str)
        except (TypeError, ValueError):
            self.log("Invalid battery capacity or buffer limit value", level="ERROR")
            return
        self.BATTERY_CAPACITY = battery_capacity
        self.LOWER_BATTERY_LIMIT = buffer_limit
        
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

        # Use stored forecasts (C_t,S_t,P_t) - now in STEP resolution (kW for power)
        C_t = self.consumption_forecast
        S_t = self.solar_forecast
        P_t = self.price_forecast

        delta = self.DELTA_HOURS  # fraction of hour per timestep

        # Log the forecasts per hour for debugging
        self.log("Forecasts per hour:")
        now = get_now_time()
        for t in range(self.T):
            forecast_time = now + datetime.timedelta(minutes=self.STEP_MINUTES * t)
            hour = forecast_time.hour
            self.log(
                f"Hour {hour:02d}: "
                f"Consumption = {C_t[t]:.2f} kW, "
                f"Solar = {S_t[t]:.2f} kW, "
                f"Price = {P_t[t]:.2f} ct/kWh"
            )

        # Initialize the optimization problem
        prob = pulp.LpProblem("Battery_Optimization", pulp.LpMinimize)

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
        FullCharge = pulp.LpVariable.dicts("FullCharge", (t for t in range(self.T)), cat="Binary")

        # Objective: price * import_power * delta - feed_in * export_power * delta  - value of final SoC
        if len(P_t) == 0:
            self.error("Empty price forecast, aborting optimization.")
            return
        P_end = np.min(P_t)
        prob += pulp.lpSum([P_t[t] * G[t] * delta - self.FEED_IN_TARIFF * E[t] * delta for t in range(self.T)]) - P_end * SoC[self.T]

        # Initial SoC
        prob += SoC[0] == SoC_0

        # ensure big-M is defined
        M = self.BATTERY_CAPACITY * 2

        for t in range(self.T):
            # Power balance (kW) at timestep t
            prob += (
                S_t[t] + G[t] + Dch[t] * self.BATTERY_EFFICIENCY
                == C_t[t] + Ch_solar[t] + Ch_grid[t] + E[t],
                f"Energy_Balance_{t}",
            )

            # SoC update: convert powers to energy via delta
            prob += (
                SoC[t + 1]
                == SoC[t]
                + (Ch_solar[t] + Ch_grid[t]) * self.BATTERY_EFFICIENCY * delta
                - Dch[t] * delta,
                f"SoC_Update_{t}",
            )

            # SoC bounds (already bounded by var bounds but keep explicit)
            prob += SoC[t + 1] >= self.LOWER_BATTERY_LIMIT, f"SoC_Min_{t}"
            prob += SoC[t + 1] <= self.BATTERY_CAPACITY, f"SoC_Max_{t}"

            # Charging limits in kW
            prob += (Ch_solar[t] + Ch_grid[t] <= self.CHARGE_RATE_MAX, f"Charge_Rate_Limit_{t}")
            prob += Ch_solar[t] <= S_t[t], f"Charge_Solar_Limit_Actual_Solar_{t}"

            # Discharging limits in kW
            prob += Dch[t] <= self.DISCHARGE_RATE_MAX, f"Discharge_Rate_Limit_{t}"

            # Surplus solar constraints (kW)
            prob += Surplus_solar[t] >= S_t[t] - C_t[t], f"Surplus_Solar_Definition_{t}"
            prob += Surplus_solar[t] >= 0, f"Surplus_Solar_NonNegative_{t}"
            prob += Ch_solar[t] <= Surplus_solar[t], f"Solar_Charging_Limit_{t}"

            # Charging from grid cannot exceed grid import (kW)
            prob += Ch_grid[t] <= G[t], f"Grid_Charging_Limit_{t}"

            # Grid export non-negative and only when full
            prob += E[t] >= 0, f"Grid_Export_NonNegative_{t}"
            prob += SoC[t + 1] >= self.BATTERY_CAPACITY - (1 - FullCharge[t]) * M, f"SoC_FullCharge_Link_{t}"
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
            forecast_time = now + datetime.timedelta(minutes=self.STEP_MINUTES * t)
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
		# Neuer Ablauf: pro Tag (00:00..23:45) ausschliesslich Tages‑Slots verwenden
        now = get_now_time()
        forecast_date = now.date()
        self.log(f"Identify cheapest windows for forecast start {now.isoformat()} (date {forecast_date}).")

        cheap_windows_data = self.load_cheap_windows()

        steps_per_hour = int(60 // self.STEP_MINUTES)
        slots_per_day = 24 * steps_per_hour

        # read raw day lists from sensor attributes
        price_days_raw = [
            self.get_state(self.PRICE_FORECAST_SENSOR, attribute="today") or [],
            self.get_state(self.PRICE_FORECAST_SENSOR, attribute="tomorrow") or [],
            self.get_state(self.PRICE_FORECAST_SENSOR, attribute="day_after_tomorrow") or [],
        ]

        # store per-window-size ISO timestamps (per day, only 00:00..23:45)
        windows_out = {f"cheapest_dates_{h}": [] for h in range(1, 9)}

        for day_idx, raw_list in enumerate(price_days_raw):
            if not raw_list:
                self.log(f"No price data for day index {day_idx}. Skipping.")
                continue

            # extract exactly slots_per_day entries for the day (if available)
            day_prices = []
            for i in range(min(slots_per_day, len(raw_list))):
                try:
                    day_prices.append(float(raw_list[i].get("total", 0)) * 100.0)
                except Exception:
                    day_prices.append(0.0)

            if len(day_prices) < 1:
                continue

            # day's midnight (local tz)
            day_date = now.date() + datetime.timedelta(days=day_idx)
            day_start = datetime.datetime(day_date.year, day_date.month, day_date.day, 0, 0, tzinfo=tzlocal.get_localzone())

            # for each window length in hours find the cheapest contiguous window inside this day
            for h in range(1, 9):
                window_steps = h * steps_per_hour
                if window_steps > len(day_prices):
                    continue
                indices = self.find_cheapest_windows(day_prices, window_steps)
                if not indices:
                    continue
                # indices is contiguous list for the window; save each step as ISO inside this day
                for idx in indices:
                    ts = day_start + datetime.timedelta(minutes=idx * self.STEP_MINUTES)
                    windows_out[f"cheapest_dates_{h}"].append(ts.isoformat())

        # Save when new forecast day and after 16:00 (same policy)
        if (cheap_windows_data.get("forecast_date") != forecast_date.isoformat()) and (now.hour > 16):
            self.save_cheap_windows(forecast_date, windows_out)
            self.log(f"Saved new cheap windows for {forecast_date}: { {k: len(v) for k,v in windows_out.items()} }")
        else:
            # if not saving, prefer loaded windows if present
            loaded_windows = cheap_windows_data.get("windows", {})
            if loaded_windows:
                windows_out = loaded_windows
                self.log(f"Using existing cheap windows from file for {forecast_date}.")
            else:
                self.log("No existing cheap windows file found; using computed windows (no save).")

        # populate flags for current horizon
        for h in range(1, 9):
            setattr(self, f"within_cheapest_{h}_hour" if h == 1 else f"within_cheapest_{h}_hours", [False] * self.T)

        for h in range(1, 9):
            iso_list = windows_out.get(f"cheapest_dates_{h}", [])
            for iso in iso_list:
                try:
                    dt = datetime.datetime.fromisoformat(iso)
                    rel = dateToRelativeHour(dt)
                    if 0 <= rel < self.T:
                        attr = f"within_cheapest_{h}_hour" if h == 1 else f"within_cheapest_{h}_hours"
                        getattr(self, attr)[rel] = True
                except Exception:
                    continue

        self.log("identify_cheapest_hours completed.")
        return

    def identify_most_expensive_hours(self):
		# analog zur cheap-Implementierung, nur mit find_most_expensive_windows
        now = get_now_time()
        forecast_date = now.date()
        self.log(f"Identify most expensive windows for forecast start {now.isoformat()} (date {forecast_date}).")

        expensive_windows_data = self.load_expensive_windows()

        steps_per_hour = int(60 // self.STEP_MINUTES)
        slots_per_day = 24 * steps_per_hour

        price_days_raw = [
            self.get_state(self.PRICE_FORECAST_SENSOR, attribute="today") or [],
            self.get_state(self.PRICE_FORECAST_SENSOR, attribute="tomorrow") or [],
            self.get_state(self.PRICE_FORECAST_SENSOR, attribute="day_after_tomorrow") or [],
        ]

        windows_out = {f"most_expensive_dates_{h}": [] for h in range(1, 9)}

        for day_idx, raw_list in enumerate(price_days_raw):
            if not raw_list:
                self.log(f"No price data for day index {day_idx}. Skipping.")
                continue

            day_prices = []
            for i in range(min(slots_per_day, len(raw_list))):
                try:
                    day_prices.append(float(raw_list[i].get("total", 0)) * 100.0)
                except Exception:
                    day_prices.append(0.0)

            if len(day_prices) < 1:
                continue

            day_date = now.date() + datetime.timedelta(days=day_idx)
            day_start = datetime.datetime(day_date.year, day_date.month, day_date.day, 0, 0, tzinfo=tzlocal.get_localzone())

            for h in range(1, 9):
                window_steps = h * steps_per_hour
                if window_steps > len(day_prices):
                    continue
                indices = self.find_most_expensive_windows(day_prices, window_steps)
                if not indices:
                    continue
                for idx in indices:
                    ts = day_start + datetime.timedelta(minutes=idx * self.STEP_MINUTES)
                    windows_out[f"most_expensive_dates_{h}"].append(ts.isoformat())

        if (expensive_windows_data.get("forecast_date") != forecast_date.isoformat()) and (now.hour > 16):
            self.save_expensive_windows(forecast_date, windows_out)
            self.log(f"Saved new expensive windows for {forecast_date}: { {k: len(v) for k,v in windows_out.items()} }")
        else:
            loaded = expensive_windows_data.get("windows", {})
            if loaded:
                windows_out = loaded
                self.log(f"Using existing expensive windows from file for {forecast_date}.")
            else:
                self.log("No existing expensive windows file found; using computed windows (no save).")

        # populate flags
        for h in range(1, 9):
            setattr(self, f"within_most_expensive_{h}_hour" if h == 1 else f"within_most_expensive_{h}_hours", [False] * self.T)

        for h in range(1, 9):
            iso_list = windows_out.get(f"most_expensive_dates_{h}", [])
            for iso in iso_list:
                try:
                    dt = datetime.datetime.fromisoformat(iso)
                    rel = dateToRelativeHour(dt)
                    if 0 <= rel < self.T:
                        attr = f"within_most_expensive_{h}_hour" if h == 1 else f"within_most_expensive_{h}_hours"
                        getattr(self, attr)[rel] = True
                except Exception:
                    continue

        self.log("identify_most_expensive_hours completed.")
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
            # fixed logging line (was an unterminated f-string causing SyntaxError)
            self.log(f"solar_forecast[{t}] = {self.solar_forecast[t]}")
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

        # Update sensors — find current timestamp aligned to STEP_MINUTES
        now_iso = now.isoformat()
        for sensor_id, data in forecasts.items():
            # Get the current value for the sensor's state (matching STEP-aligned timestamp)
            current_value = None
            for item in data:
                if item[0] == now_iso:
                    current_value = item[1]
                    break

            # If no current value is found, use the first forecast entry (fallback)
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
            state=self._format_forecast_value(charge_grid_session),
            attributes={
                "session_start": session_start.isoformat() if session_start else None,
                "session_duration": session_duration,
            },
        )

        self.log(
            f'Set state "{self._format_forecast_value(charge_grid_session)}" '
            f'for self.SENSOR_CHARGE_GRID_SESSION.'
        )
        self.log(
            f"Session Start: {session_start.isoformat() if session_start else None}, "
            f"Session Duration: {session_duration}"
        )

        # Update the Forecast Time Horizon
        try:
            hours = self.T * self.DELTA_HOURS
        except Exception:
            hours = float(self.T) * (self.STEP_MINUTES / 60.0)
        # Set sensor state to hours (readable) and provide steps + hours as attributes
        hours_rounded = round(hours, 2)
        self.set_state(
            self.SENSOR_FORECAST_HORIZON,
            state=str(hours_rounded),
            attributes={"steps": int(self.T), "hours": hours},
        )

    def find_cheapest_windows(self, prices, window_size):
        """
        Finds the start index of the cheapest consecutive window of the given size (window_size in steps).

        Args:
            prices (list of float): List of prices in ct/kWh (one entry per STEP_MINUTES).
            window_size (int): Size of the window in steps (e.g. 1 hour -> 4 steps if STEP_MINUTES=15).

        Returns:
            list of int: List of indices that are within the cheapest window (step indices).
        """
        self.log(
            f"Finding cheapest window of {window_size} steps with max price threshold {self.MAX_PRICE_THRESH_CT} ct/kWh."
        )
        # Guard: if window_size invalid or too large, return empty list
        if window_size <= 0 or window_size > len(prices):
            self.log(f"find_cheapest_windows: window_size {window_size} invalid for prices length {len(prices)}. Returning [].")
            return []
        min_total = float("inf")
        min_start = 0
        for i in range(len(prices) - window_size + 1):
            window = prices[i : i + window_size]
            # Skip window if any step exceeds the threshold
            if any(price > self.MAX_PRICE_THRESH_CT for price in window):
                self.log(
                    f"Skipping window {i}..{i + window_size - 1} due to high price in window."
                )
                continue
            window_total = sum(window)
            if window_total < min_total:
                min_total = window_total
                min_start = i
        self.log(
            f"Cheapest window (steps): {min_start} - {min_start + window_size - 1}."
        )
        return list(range(min_start, min_start + window_size))

    def find_most_expensive_windows(self, prices, window_size):
        """
        Finds the start index of the most expensive consecutive window of the given size (window_size in steps).

        Args:
            prices (list of float): List of prices in ct/kWh (one entry per STEP_MINUTES).
            window_size (int): Size of the window in steps.

        Returns:
            list of int: List of indices that are within the most expensive window (step indices).
        """
        self.log(f"Finding most expensive window of {window_size} steps.")
        # Guard: if window_size invalid or too large, return empty list
        if window_size <= 0 or window_size > len(prices):
            self.log(f"find_most_expensive_windows: window_size {window_size} invalid for prices length {len(prices)}. Returning [].")
            return []
        max_total = float("-inf")
        max_start = 0
        for i in range(len(prices) - window_size + 1):
            window = prices[i : i + window_size]
            window_total = sum(window)
            if window_total > max_total:
                max_total = window_total
                max_start = i
        self.log(
            f"Most expensive window (steps): {max_start} - {max_start + window_size - 1}."
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
            windows (dict): Contains lists of indices for windows.
        """
        data = {"forecast_date": forecast_date.isoformat(), "windows": windows}
        try:
            with open(self.EXPENSIVE_WINDOWS_FILE, "w") as f:
                json.dump(data, f)
                self.log("Expensive window assignments saved.")
        except Exception as e:
            self.error(f"Error saving expensive window assignments: {e}")


def relativeHourToDate(hour: int) -> datetime.datetime:
    # interpret `hour` as number of steps; use configured STEP_MINUTES when available
    step = 15
    try:
        step = WattWise.__dict__.get("STEP_MINUTES", 15)
    except Exception:
        step = 15
    now = get_now_time()
    new_time = now + timedelta(minutes=hour * int(step))
    return new_time


def dateToRelativeHour(date: datetime.datetime) -> int:
    # returns number of steps between now and date (positive if future)
    step = 15
    try:
        step = WattWise.__dict__.get("STEP_MINUTES", 15)
    except Exception:
        step = 15
    now = get_now_time()
    delta = date - now
    steps = delta.total_seconds() // (int(step) * 60)
    return int(steps)


def get_now_time():
    # return current time rounded DOWN to nearest STEP_MINUTES (default 15)
    now = datetime.datetime.now(tzlocal.get_localzone())
    step = 15
    try:
        # if running as method, WattWise may set STEP_MINUTES; but keep default 15 for module-level fallback
        step = getattr(WattWise, "STEP_MINUTES", 15)
    except Exception:
        step = 15
    minute = (now.minute // step) * step
    now_rounded = now.replace(minute=minute, second=0, microsecond=0)
    return now_rounded


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
