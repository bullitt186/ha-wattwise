# Design Document

## Overview

WattWise is implemented as a native Home Assistant custom integration that provides intelligent battery optimization. The system uses a linear programming approach with the PuLP library to solve a Mixed Integer Linear Programming (MILP) problem that minimizes energy costs while respecting physical and operational constraints.

The architecture follows Home Assistant's integration patterns with proper component separation, configuration flows, and entity management. The system operates on an hourly schedule using Home Assistant's native scheduler but can be triggered manually through service calls, making it responsive to changing conditions while maintaining predictable operation.

## Architecture

### Home Assistant Integration Structure

The integration follows Home Assistant's standard integration architecture:

```
custom_components/wattwise/
├── __init__.py              # Integration setup and coordinator
├── manifest.json            # Integration metadata and dependencies
├── config_flow.py           # Configuration and options flows
├── const.py                 # Constants and configuration schemas
├── coordinator.py           # Data update coordinator
├── sensor.py                # Sensor platform
├── binary_sensor.py         # Binary sensor platform
├── services.yaml            # Service definitions
├── strings.json             # UI strings for configuration
└── translations/            # Localization files
    └── en.json
```

### Core Components

1. **Integration Entry Point** (`__init__.py`): Manages integration lifecycle, platform loading, and coordinator setup
2. **Configuration Flow** (`config_flow.py`): Implements ConfigFlow and OptionsFlow for UI-based setup
3. **Data Update Coordinator** (`coordinator.py`): Manages data fetching, optimization scheduling, and entity updates
4. **Entity Platforms**: Sensor and binary sensor platforms following Home Assistant entity patterns
5. **Services**: Registered Home Assistant services with proper schemas
6. **Constants and Schemas** (`const.py`): Configuration validation and integration constants

### Integration Points

- **Home Assistant Core**: Native integration with entity registry, device registry, and configuration system
- **Entity Registry**: Proper entity registration with unique IDs and device association
- **Configuration System**: ConfigFlow and OptionsFlow for user-friendly setup
- **Data Update Coordinator**: Efficient data fetching and entity state management
- **Storage API**: Home Assistant's storage system for persistent data
- **Service Registry**: Registered services with proper schemas and validation
- **Recorder Integration**: Historical data access through Home Assistant's recorder
- **External APIs**: Tibber and Solcast data through existing Home Assistant integrations

### Data Flow

```
[Config Flow] → [Integration Setup] → [Coordinator Setup] → [Entity Platform Registration]
                                            ↓
[Entity States] → [Coordinator Update] → [Optimization Engine] → [Entity State Updates]
                                            ↓                           ↓
                    [HA Storage API] ← [Historical Data]    [Service Calls] → [Automations]
                                            ↓                           ↓
                                    [Price Windows]              [Battery Hardware]
```

### Home Assistant Integration Lifecycle

1. **Installation**: User installs via HACS or manual installation
2. **Configuration**: ConfigFlow guides user through entity selection and parameter setup
3. **Integration Setup**: `async_setup_entry` initializes coordinator and loads platforms
4. **Entity Registration**: Platforms register entities with proper device and unique ID association
5. **Data Updates**: Coordinator manages scheduled and manual optimization runs
6. **Service Calls**: Users can trigger manual optimization through registered services
7. **Options Updates**: OptionsFlow allows runtime configuration changes
8. **Unload**: `async_unload_entry` properly cleans up resources

## Components and Interfaces

### Integration Architecture

**Integration Setup Functions** (`__init__.py`):
```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WattWise from a config entry."""
    
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
```

**WattWiseConfigFlow Class** (`config_flow.py`):
```python
class WattWiseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WattWise."""
    VERSION = 1
    
class WattWiseOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for WattWise."""
```

**WattWiseCoordinator Class** (`coordinator.py`):
```python
class WattWiseCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API and optimization."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        
    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint and run optimization."""
```

**Configuration Schema** (`const.py`):
```python
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

DOMAIN = "wattwise"

CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_BATTERY_CAPACITY): vol.Coerce(float),
    vol.Required(CONF_BATTERY_EFFICIENCY): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1.0)),
    vol.Required(CONF_CHARGE_RATE_MAX): vol.Coerce(float),
    vol.Required(CONF_DISCHARGE_RATE_MAX): vol.Coerce(float),
    vol.Optional(CONF_LOWER_BATTERY_LIMIT, default=1.0): vol.Coerce(float),
    vol.Optional(CONF_TIME_HORIZON, default=48): vol.All(int, vol.Range(min=12, max=72)),
    vol.Optional(CONF_CONSUMPTION_HISTORY_DAYS, default=7): vol.All(int, vol.Range(min=1, max=30)),
    vol.Optional(CONF_FEED_IN_TARIFF, default=7.0): vol.Coerce(float),
    vol.Optional(CONF_MAX_PRICE_THRESHOLD, default=80.0): vol.Coerce(float),
    vol.Required(CONF_CONSUMPTION_SENSOR): cv.entity_id,
    vol.Required(CONF_SOLAR_FORECAST_TODAY): cv.entity_id,
    vol.Required(CONF_SOLAR_FORECAST_TOMORROW): cv.entity_id,
    vol.Required(CONF_BATTERY_SOC_SENSOR): cv.entity_id,
})

# Service schemas
SERVICE_OPTIMIZE_BATTERY = "optimize_battery"
SERVICE_SCHEMA_OPTIMIZE = vol.Schema({})
```

### Data Collection Module

**Consumption Forecasting**:
- Loads historical consumption data from JSON file
- Fetches new data using Home Assistant history API
- Calculates hourly averages based on configurable history period
- Maintains rolling window of historical data

**Solar Production Forecasting**:
- Retrieves detailed hourly forecasts from Solcast integration
- Combines today's and tomorrow's forecast data
- Maps forecast periods to optimization time horizon
- Handles missing or incomplete forecast data

**Energy Price Forecasting**:
- Fetches current and future prices from Tibber API via Home Assistant sensor
- Converts EUR/kWh to ct/kWh for consistency
- Combines today's and tomorrow's pricing data
- Truncates time horizon based on available price data

### Optimization Engine

**Linear Programming Formulation**:

**Decision Variables**:
- `G[t]`: Grid import at time t (kW)
- `Ch_solar[t]`: Battery charging from solar at time t (kW)
- `Ch_grid[t]`: Battery charging from grid at time t (kW)
- `Dch[t]`: Battery discharge at time t (kW)
- `SoC[t]`: State of charge at time t (kWh)
- `E[t]`: Grid export at time t (kW)
- `FullCharge[t]`: Binary variable indicating full battery (0/1)

**Objective Function**:
```
Minimize: Σ(P[t] × G[t] - feed_in_tariff × E[t]) - P_min × SoC[T]
```

**Key Constraints**:
1. Energy balance: `S[t] + G[t] + Dch[t] × η = C[t] + Ch_solar[t] + Ch_grid[t] + E[t]`
2. SoC dynamics: `SoC[t+1] = SoC[t] + (Ch_solar[t] + Ch_grid[t]) × η - Dch[t]`
3. Battery limits: `lower_limit ≤ SoC[t] ≤ capacity`
4. Rate limits: `Ch_solar[t] + Ch_grid[t] ≤ charge_rate_max`, `Dch[t] ≤ discharge_rate_max`
5. Solar constraints: `Ch_solar[t] ≤ max(0, S[t] - C[t])`

### Entity Platform Management

**Sensor Platform** (`sensor.py`):
```python
class WattWiseSensor(CoordinatorEntity, SensorEntity):
    """Base WattWise sensor."""
    
    def __init__(self, coordinator: WattWiseCoordinator, description: SensorEntityDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info
```

**Binary Sensor Platform** (`binary_sensor.py`):
```python
class WattWiseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base WattWise binary sensor."""
    
    def __init__(self, coordinator: WattWiseCoordinator, description: BinarySensorEntityDescription) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info
```

**Device Information**:
```python
device_info = DeviceInfo(
    identifiers={(DOMAIN, entry.entry_id)},
    name="WattWise Battery Optimizer",
    manufacturer="WattWise",
    model="Battery Optimization System",
    sw_version="1.0.0",
)
```

**Services Registration** (`__init__.py`):
```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WattWise from a config entry."""
    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_OPTIMIZE_BATTERY,
        coordinator.async_optimize_battery,
        schema=SERVICE_SCHEMA_OPTIMIZE,
    )
```

### Price Window Analysis

**Cheap Window Identification**:
- Sorts forecast prices excluding those above maximum threshold
- Identifies cheapest N-hour windows for N=1 to 8
- Updates binary sensors indicating current time within cheap windows
- Stores window data to persistent file for reference

**Expensive Window Identification**:
- Identifies most expensive N-hour windows for N=1 to 8
- Updates binary sensors for expensive periods
- Used for discharge timing optimization

## Data Models

### Data Models

**Configuration Data**:
```python
@dataclass
class WattWiseConfigData:
    """Configuration data for WattWise."""
    battery_capacity: float
    battery_efficiency: float
    charge_rate_max: float
    discharge_rate_max: float
    time_horizon: int
    feed_in_tariff: float
    consumption_history_days: int
    lower_battery_limit: float
    max_price_threshold_ct: float
    consumption_sensor: str
    solar_forecast_sensor_today: str
    solar_forecast_sensor_tomorrow: str
    battery_soc_sensor: str

# Type alias for config entry
WattWiseConfigEntry = ConfigEntry[WattWiseConfigData]
```

**Manifest Configuration** (`manifest.json`):
```json
{
  "domain": "wattwise",
  "name": "WattWise Battery Optimization",
  "codeowners": ["@your-username"],
  "config_flow": true,
  "dependencies": ["recorder"],
  "documentation": "https://github.com/your-repo/wattwise",
  "integration_type": "service",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/your-repo/wattwise/issues",
  "requirements": ["pulp>=2.7.0", "numpy>=1.21.0"],
  "version": "1.0.0"
}
```

### Forecast Data Model
```python
@dataclass
class ForecastData:
    consumption_forecast: List[float]  # kW per hour
    solar_forecast: List[float]        # kW per hour
    price_forecast: List[float]        # ct/kWh per hour
    time_horizon: int                  # Actual horizon used
```

### Optimization Results Model
```python
@dataclass
class OptimizationResults:
    charge_solar_schedule: List[float]    # kW per hour
    charge_grid_schedule: List[float]     # kW per hour
    discharge_schedule: List[float]       # kW per hour
    soc_schedule: List[float]            # kWh per hour
    grid_import_schedule: List[float]     # kW per hour
    grid_export_schedule: List[float]     # kW per hour
    full_charge_schedule: List[bool]      # Binary per hour
```

### Historical Data Model
```python
@dataclass
class ConsumptionHistoryEntry:
    last_changed: str      # ISO format timestamp
    state: str            # Consumption value as string
    last_updated: str     # ISO format timestamp
```

## Error Handling

### Data Availability Issues
- **Missing Sensor Data**: Log warning and use default values or skip optimization
- **Incomplete Forecasts**: Truncate time horizon to available data
- **API Failures**: Retry with exponential backoff, fall back to cached data
- **File System Errors**: Create new files if missing, log errors for corruption

### Optimization Failures
- **Infeasible Problem**: Log constraint conflicts, maintain previous schedule
- **Solver Errors**: Fall back to simple heuristic charging schedule
- **Timeout Issues**: Use partial results if available, reduce time horizon

### Integration Errors
- **Entity State Access**: Handle unavailable entities gracefully with fallback values
- **Entity Update Failures**: Use Home Assistant's entity update mechanisms with proper error handling
- **Configuration Errors**: Validate through config flow, prevent invalid configurations from being saved

## Testing Strategy

### Unit Testing
- **Forecast Data Processing**: Test data parsing, averaging, and time alignment
- **Optimization Logic**: Test constraint formulation and objective function
- **Price Window Analysis**: Test sorting and window identification algorithms
- **Configuration Validation**: Test parameter validation and default handling

### Integration Testing
- **Home Assistant Integration**: Use Home Assistant test framework for entity and service testing
- **Storage Operations**: Test Home Assistant storage API for history data persistence
- **Coordinator Updates**: Test data update coordinator scheduling and manual triggers
- **Config Flow**: Test configuration flow UI and validation
- **End-to-End Optimization**: Test complete workflow with mocked entity states

### Performance Testing
- **Optimization Speed**: Ensure solutions complete within reasonable time
- **Memory Usage**: Monitor memory consumption with large historical datasets
- **Concurrent Operations**: Test behavior under simultaneous manual and scheduled runs

### Hardware Integration Testing
- **Battery Control**: Test with simulated and real battery systems
- **Automation Triggers**: Verify Home Assistant automations respond correctly
- **Sensor Accuracy**: Validate sensor values match optimization results

## Security Considerations

### API Security
- Home Assistant long-lived access tokens stored in configuration
- Tibber API tokens stored in Home Assistant secrets
- No sensitive data logged in plain text

### Storage Security
- History data stored using Home Assistant's secure storage API
- Data files contain only consumption data and timestamps
- No user credentials or sensitive configuration in stored data
- Integration follows Home Assistant's data protection guidelines

### Network Security
- All API communication over HTTPS
- Local Home Assistant communication over configured protocol
- No external network access beyond required APIs