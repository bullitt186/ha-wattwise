# Scope

What this project is for, so contributions go in the same direction. Changing this file is a
maintainer decision, recorded as an ADR in the same pull request (PR hygiene checks this).

## Purpose

Home Assistant users with a home battery, solar panels and a dynamic electricity tariff want the
battery to charge and discharge at the cheapest times without planning it by hand. WattWise is an
AppDaemon app that forecasts consumption, solar production and prices, optimises the battery
schedule over 48 hours with linear programming, and exposes the plan and its switches as Home
Assistant entities ([README](../README.md#how-it-works)).

## In scope

- The optimisation of grid charging, solar charging and discharging of one home battery, every
  15 minutes, within the battery's capacity and charge/discharge rates.
- Forecast inputs from Home Assistant sensors: consumption history, Solcast solar forecasts and
  EPEX Spot prices ([Prerequisites](../README.md#prerequisites)).
- Home Assistant entities, example automations and the ApexCharts card that show and apply the
  plan.

## Out of scope

- Controlling the battery inverter directly: WattWise sets Home Assistant switches, and the
  user's own automations act on the inverter (see the example automations), because each system
  is controlled differently.
- Anything else: Open: to be decided by the maintainer.

## Direction

Open: to be decided by the maintainer. Open requests are in the
[issues](https://github.com/bullitt186/ha-wattwise/issues).

## Principles

- Configuration over code: system-specific constants and entity IDs live in `apps.yaml`, not in
  `wattwise.py`.
- Runs inside the AppDaemon add-on with the packages listed in the README; nothing else to host.
