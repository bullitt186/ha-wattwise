# WattWise 
WattWise is an AppDaemon application for [Home Assistant](https://www.home-assistant.io/)  that intelligently optimizes battery usage based on consumption forecasts, solar production forecasts, and dynamic energy prices. By leveraging historical data and real-time information, it schedules battery charging and discharging actions to minimize energy costs and maximize efficiency, providing seamless integration and real-time monitoring through Home Assistant's interface.

## Table of Contents 
 
- [Features](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#features)
 
- [How It Works](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#how-it-works)
 
- [Getting Started](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#getting-started)  
  - [Prerequisites](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#prerequisites)
 
  - [Installation](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#installation)
 
- [Configuration](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#configuration)  
  - [Home Assistant Setup](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#home-assistant-setup)
 
  - [AppDaemon Setup](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#appdaemon-setup)
 
  - [Customizing WattWise](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#customizing-wattwise)
 
- [Usage](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#usage)  
  - [Visualizing Forecasts](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#visualizing-forecasts)
 
- [Contributing]()
 
- [License](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#license)
 
- [Contact](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#contact)
 
- [Acknowledgements](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#acknowledgements)

## Features 
 
- **Hourly Optimization** : Executes the optimization process every hour to ensure decisions are based on the latest data.
 
- **Dynamic Forecasting** : Utilizes historical consumption data, solar production forecasts, and real-time energy prices.
 
- **Automated Charging & Discharging** : Schedules battery charging from the grid or solar and discharging to the house based on optimization results.
 
- **Real-Time Monitoring** : Updates Home Assistant sensors with current values and forecast data for comprehensive monitoring.
 
- **Customizable Parameters** : Adjust battery capacity, charge/discharge rates, tariffs, and more to fit your specific setup.
 
- **User-Friendly Visualization** : Integrates with [ApexCharts](https://github.com/RomRider/apexcharts-card)  for intuitive graphical representations of forecasts and actions.

## How It Works 

WattWise leverages linear programming to optimize the charging and discharging schedule of your home battery system. Here's a detailed explanation of the process:
 
1. **Data Collection** : 
  - **Consumption Forecast** : Calculates average consumption for each hour based on historical data from the past seven days.
 
  - **Solar Production Forecast** : Retrieves solar production forecasts for today and tomorrow from Home Assistant sensors.
 
  - **Energy Price Forecast** : Obtains current and future energy prices, considering both today's and tomorrow's rates.
 
2. **Optimization Algorithm** : 
  - **Objective** : Minimizes the total energy cost over a 24-hour horizon by determining the optimal times to charge (from solar or grid) and discharge the battery.
 
  - **Constraints** : 
    - **Battery Capacity** : Ensures the battery state of charge (SoC) stays within physical limits.
 
    - **Charge/Discharge Rates** : Respects maximum charge and discharge rates of the battery system.
 
    - **Energy Balance** : Maintains a balance between consumption, production, and battery/storage actions.
 
    - **Grid Interactions** : Manages energy import/export to/from the grid, considering feed-in tariffs.
 
3. **Scheduling Actions** : 
  - **Charging from Grid** : Schedules charging during periods of low energy prices or when solar production is insufficient.
 
  - **Discharging to House** : Schedules discharging during periods of high consumption or high energy prices.
 
  - **Updating States** : Adjusts Home Assistant sensors to reflect the optimized schedule and current statuses.
 
4. **Real-Time Updates** : 
  - **Sensor States** : Updates custom sensors with current values and forecasts, providing real-time insights.
 
  - **Visualization** : Enables graphical representations through ApexCharts for better understanding and monitoring.

## Getting Started 

### Prerequisites 
 
- **Home Assistant** : A running instance of Home Assistant.
 
- **AppDaemon** : Install [AppDaemon 4](https://appdaemon.readthedocs.io/en/latest/) .
 
- **Python 3.7+** : Required for running AppDaemon and the WattWise script.
 
- **Dependencies** : 
  - `pulp`
 
  - `numpy`
 
  - `requests`
 
  - `pytz`

### Installation 
 
1. **Clone the Repository** 

```bash
git clone https://github.com/yourusername/WattWise.git
cd WattWise
```
 
2. **Install Dependencies** 
It's recommended to use a virtual environment:


```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
*Alternatively, install dependencies globally:*

```bash
pip install appdaemon pulp numpy requests pytz
```
 
3. **Place the Python Script**  
  - Ensure `battery_optimizer.py` (the WattWise script) is placed in your AppDaemon apps directory (e.g., `/config/appdaemon/apps/`).
 
4. **Configure WattWise**  
  - Create a configuration file named `wattwise.yaml` in your AppDaemon apps directory with the necessary settings (see [AppDaemon Setup](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#appdaemon-setup) ).
 
5. **Configure Home Assistant Sensors**  
  - Add custom sensors to your Home Assistant configuration (see [Home Assistant Setup](https://chatgpt.com/c/6703ba73-6984-8009-874b-94029eb4ff48#home-assistant-setup) ).
 
6. **Restart Services**  
  - **Home Assistant** : Restart to apply sensor configurations.
 
  - **AppDaemon** : Restart to load the WattWise application.

## Configuration 

Proper configuration is essential for WattWise to function correctly. Below are the key areas you need to configure.

### Home Assistant Setup 

Create custom sensors in Home Assistant to store the optimization data and forecasts. These sensors will be updated by WattWise to reflect current states and future schedules.
 
- **Sensors** : For storing numerical data like battery charge levels, grid import/export, consumption forecasts, etc.
 
- **Binary Sensors** : For storing on/off states like whether the battery is charging or discharging.
Ensure these sensors are defined in your Home Assistant configuration (e.g., `configuration.yaml` or an included file).
### AppDaemon Setup 
Configure WattWise in AppDaemon by creating a `wattwise.yaml` file in your AppDaemon apps directory. This file contains important settings that control how WattWise operates.Example `wattwise.yaml` Configuration:** 

```yaml
wattwise:
  module: battery_optimizer
  class: WattWise
  ha_url: "http://homeassistant.local:8123"
  token: "YOUR_LONG_LIVED_ACCESS_TOKEN"
```
**Parameters Explained:**  
- `module`: The name of the Python script without the `.py` extension (should match `battery_optimizer` if your script is named `battery_optimizer.py`).
 
- `class`: The name of the main class in the Python script (`WattWise`).
 
- `ha_url`: The URL of your Home Assistant instance.
 
- `token`: A long-lived access token from Home Assistant for API access.

### Customizing WattWise 
You can adjust various parameters within the `battery_optimizer.py` script to match your specific setup: 
- **Battery Parameters** : 
  - `BATTERY_CAPACITY`: Total capacity of your battery in kWh.
 
  - `BATTERY_EFFICIENCY`: Efficiency factor of your battery (0 < efficiency ≤ 1).
 
  - `CHARGE_RATE_MAX`: Maximum charging rate in kW.
 
  - `DISCHARGE_RATE_MAX`: Maximum discharging rate in kW.
 
- **Time Horizon** : 
  - `TIME_HORIZON`: Number of hours to look ahead in the optimization (default is 24 hours).
 
- **Tariffs and Prices** : 
  - `FEED_IN_TARIFF`: Price for feeding energy back to the grid in ct/kWh.
 
- **Entity IDs** : 
  - Update the entity IDs in the script to match your Home Assistant sensors and switches. Key entities include: 
    - **Consumption Sensor** : Represents your house's energy consumption.
 
    - **Solar Forecast Sensors** : For today and tomorrow's solar production forecasts.
 
    - **Price Forecast Sensor** : Contains the energy price forecast data.
 
    - **Battery State of Charge Sensor** : Indicates the current charge level of the battery.
 
    - **Battery Charger/Discharger Switches** : Controls for charging and discharging the battery.
**Note** : After making changes to the script, restart AppDaemon to apply the updates.
## Usage 

Once installed and configured, WattWise automatically runs the optimization process every hour. It analyzes consumption patterns, solar production forecasts, and energy prices to determine the most cost-effective charging and discharging schedule for your battery system.

### Visualizing Forecasts 
Integrate with [ApexCharts](https://github.com/RomRider/apexcharts-card)  in Home Assistant to visualize forecast data and optimized schedules.**Example ApexCharts Configuration:** 

```yaml
type: custom:apexcharts-card
graph_span: 24h
span:
  start: hour
header:
  show: true
  title: Battery Charge from Solar Forecast
series:
  - entity: sensor.battery_charge_from_solar
    name: Charge from Solar
    type: line
    data_generator: |
      return entity.attributes.forecast.map(item => {
        return [new Date(item[0]).getTime(), item[1]];
      });
yaxis:
  - id: charging_axis
    min: 0
    max: 10
    decimals: 1
    opposite: false
```
*Repeat similar configurations for other sensors to visualize different aspects of the battery optimization.*
## Contributing 

Contributions are welcome! Whether it's reporting bugs, suggesting features, or submitting pull requests, your input helps improve WattWise.
 
1. **Fork the Repository**
 
2. **Create a Feature Branch** 

```bash
git checkout -b feature/YourFeature
```
 
3. **Commit Your Changes** 

```bash
git commit -m "Add Your Feature"
```
 
4. **Push to the Branch** 

```bash
git push origin feature/YourFeature
```
 
5. **Open a Pull Request**

Please ensure that your contributions adhere to the project's coding standards and include appropriate documentation.

## License 
This project is licensed under the [MIT License](https://chatgpt.com/c/LICENSE) .
## Contact 
 
- **Your Name**
 
- **Email** : [your.email@example.com]()
 
- **GitHub** : [yourusername](https://github.com/yourusername)

## Acknowledgements 
 
- [AppDaemon](https://appdaemon.readthedocs.io/en/latest/)
 
- [Home Assistant](https://www.home-assistant.io/)
 
- [PuLP Optimization Library]()
 
- [ApexCharts Card](https://github.com/RomRider/apexcharts-card)
 
- [Material Design Icons](https://materialdesignicons.com/)
 
- [Readme Best Practices](https://github.com/jehna/readme-best-practices)
