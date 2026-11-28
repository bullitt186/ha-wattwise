# Requirements Document

## Introduction

WattWise is an intelligent battery optimization system implemented as a Home Assistant custom integration that uses linear programming to minimize energy costs by optimally scheduling battery charging and discharging operations. The system analyzes consumption forecasts, solar production forecasts, and dynamic energy prices to determine the most cost-effective battery usage patterns over a 24-48 hour horizon. It integrates natively with Home Assistant as a HACS-installable custom integration and provides real-time monitoring, automated control, and comprehensive forecasting capabilities through native Home Assistant entities and services.

## Requirements

### Requirement 1

**User Story:** As a homeowner with a solar battery system, I want WattWise to automatically optimize my battery charging and discharging schedule based on energy prices and forecasts, so that I can minimize my electricity costs while maintaining reliable power supply.

#### Acceptance Criteria

1. WHEN the system runs hourly optimization THEN it SHALL retrieve consumption forecasts, solar production forecasts, and energy price forecasts for the next 24-48 hours
2. WHEN optimization is executed THEN the system SHALL use linear programming to determine optimal charging/discharging schedule that minimizes total energy costs
3. WHEN optimization completes THEN the system SHALL update Home Assistant sensors with current values and forecast data
4. WHEN battery reaches capacity limits THEN the system SHALL respect minimum and maximum state of charge constraints
5. WHEN charging or discharging THEN the system SHALL not exceed maximum charge/discharge rates specified in configuration

### Requirement 2

**User Story:** As a system administrator, I want to configure WattWise parameters through Home Assistant's native configuration system, so that I can customize the system for my specific battery setup and energy tariffs using the standard Home Assistant configuration flow.

#### Acceptance Criteria

1. WHEN installing the integration THEN I SHALL be able to configure battery capacity, efficiency, and charge/discharge rates through the Home Assistant configuration flow UI
2. WHEN setting up forecasting THEN I SHALL be able to configure time horizon and consumption history days through integration options
3. WHEN defining energy pricing THEN I SHALL be able to set feed-in tariff rates through the configuration flow
4. WHEN mapping sensors THEN I SHALL be able to select Home Assistant entities for consumption, solar forecast, battery SoC, and price sensors using entity selectors
5. WHEN updating configuration THEN the system SHALL reload the integration configuration and apply changes through the options flow

### Requirement 3

**User Story:** As a Home Assistant user, I want WattWise to provide comprehensive sensor data and controls through native Home Assistant entities, so that I can monitor system status and manually trigger optimizations using standard Home Assistant services.

#### Acceptance Criteria

1. WHEN the integration is loaded THEN it SHALL create native sensor and binary sensor entities following Home Assistant entity naming conventions
2. WHEN forecasts are available THEN it SHALL expose consumption and solar production forecast data through sensor attributes following Home Assistant attribute standards
3. WHEN optimization runs THEN it SHALL update entity states using Home Assistant's entity update mechanisms
4. WHEN I need manual control THEN I SHALL be able to trigger optimization through a registered Home Assistant service with proper service schema validation
5. WHEN entities are created THEN all entities SHALL be properly registered in Home Assistant's entity registry with appropriate device information and unique IDs

### Requirement 4

**User Story:** As a user with dynamic energy pricing, I want WattWise to identify the cheapest and most expensive hours for energy consumption, so that I can understand when the system will charge from grid or discharge to house.

#### Acceptance Criteria

1. WHEN energy price forecasts are available THEN the system SHALL identify the cheapest 1-8 hour windows within the forecast horizon
2. WHEN energy price forecasts are available THEN the system SHALL identify the most expensive 1-8 hour windows within the forecast horizon
3. WHEN price analysis completes THEN it SHALL update binary sensors indicating whether current time falls within cheap or expensive windows
4. WHEN prices exceed maximum threshold THEN the system SHALL exclude excessively high prices from cheap window calculations
5. WHEN price windows change THEN the system SHALL update corresponding binary sensors in real-time

### Requirement 5

**User Story:** As a homeowner, I want WattWise to maintain historical consumption data and use it for accurate forecasting, so that the optimization decisions are based on my actual usage patterns.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL load existing consumption history from persistent storage
2. WHEN new consumption data is available THEN it SHALL fetch and append data to the historical record
3. WHEN calculating forecasts THEN it SHALL use average consumption per hour based on the configured number of historical days
4. WHEN storing data THEN it SHALL automatically remove consumption data older than the configured retention period
5. WHEN history file is corrupted or missing THEN the system SHALL start with empty history and begin collecting new data

### Requirement 6

**User Story:** As a user with a solar system, I want WattWise to prioritize charging from solar production over grid charging, so that I maximize the use of my renewable energy and minimize grid dependency.

#### Acceptance Criteria

1. WHEN solar production exceeds consumption THEN the system SHALL prioritize charging battery from surplus solar energy
2. WHEN solar production is insufficient THEN the system SHALL supplement with grid charging only when economically beneficial
3. WHEN battery is full and solar surplus exists THEN the system SHALL export excess energy to the grid
4. WHEN optimizing charging THEN it SHALL respect the constraint that solar charging cannot exceed available solar production
5. WHEN calculating energy balance THEN it SHALL account for battery efficiency in charging and discharging operations

### Requirement 7

**User Story:** As a system integrator, I want WattWise to provide automation-friendly outputs that can control my specific battery hardware, so that I can integrate it with different battery management systems.

#### Acceptance Criteria

1. WHEN optimization determines charging is needed THEN it SHALL activate the battery charging switch and set appropriate charge rate sensor
2. WHEN optimization determines discharging is beneficial THEN it SHALL set maximum discharge possible sensor for hardware control
3. WHEN battery operations change THEN it SHALL update binary sensors that can trigger Home Assistant automations
4. WHEN providing control signals THEN all sensor values SHALL be in appropriate units (kW for power, kWh for energy)
5. WHEN hardware integration is needed THEN the system SHALL provide example automations for common battery systems

### Requirement 8

**User Story:** As a Home Assistant integration developer, I want WattWise to follow Home Assistant's integration architecture patterns, so that it integrates seamlessly with Home Assistant's core systems and provides a consistent user experience.

#### Acceptance Criteria

1. WHEN implementing the integration THEN it SHALL follow Home Assistant's integration structure with proper __init__.py, manifest.json, and platform files
2. WHEN creating entities THEN it SHALL use Home Assistant's entity base classes and follow entity naming conventions
3. WHEN handling configuration THEN it SHALL implement ConfigFlow and OptionsFlow following Home Assistant's configuration patterns
4. WHEN managing data updates THEN it SHALL use DataUpdateCoordinator for efficient data fetching and entity updates
5. WHEN providing services THEN it SHALL register services with proper schemas and follow Home Assistant's service patterns

### Requirement 9

**User Story:** As a user monitoring system performance, I want WattWise to provide comprehensive logging and error handling through Home Assistant's native logging system, so that I can troubleshoot issues and understand system behavior.

#### Acceptance Criteria

1. WHEN optimization runs THEN the system SHALL log detailed information about forecasts, constraints, and optimization results using Home Assistant's logging framework
2. WHEN errors occur THEN it SHALL log specific error messages with sufficient context for troubleshooting using appropriate log levels
3. WHEN sensor data is unavailable THEN it SHALL handle missing data gracefully and continue operation where possible
4. WHEN optimization fails THEN it SHALL log the failure reason and maintain previous entity states
5. WHEN integration loads THEN it SHALL log initialization status and configuration validation results through Home Assistant's startup logging