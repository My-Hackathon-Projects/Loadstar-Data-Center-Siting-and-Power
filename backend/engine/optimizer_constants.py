"""Constants and variable names for the supply optimizer."""

from typing import Literal, cast

from backend.engine.assumptions import ASSUMPTIONS

_OPTIMIZER_ASSUMPTIONS = cast(dict[str, object], ASSUMPTIONS["optimizer"])


def _float_assumption(key: str) -> float:
    value = _OPTIMIZER_ASSUMPTIONS[key]
    if isinstance(value, int | float):
        return float(value)
    raise TypeError(f"Optimizer assumption {key} must be numeric.")


def _int_assumption(key: str) -> int:
    value = _OPTIMIZER_ASSUMPTIONS[key]
    if isinstance(value, int):
        return value
    raise TypeError(f"Optimizer assumption {key} must be an integer.")


HOURS_PER_DAY = _int_assumption("optimization_horizon_hours")
BATTERY_CHARGE_EFFICIENCY = _float_assumption("battery_charge_efficiency")
BATTERY_DISCHARGE_EFFICIENCY = _float_assumption("battery_discharge_efficiency")
BACKUP_CARBON_G_KWH = _float_assumption("backup_carbon_g_kwh")

CURTAILMENT_PENALTY_EUR_MWH = _float_assumption("curtailment_penalty_eur_mwh")
GRID_IMPORT_MARGIN_EUR_MWH = _float_assumption("grid_import_margin_eur_mwh")
ONSITE_SOLAR_VARIABLE_EUR_MWH = _float_assumption("onsite_solar_variable_eur_mwh")
BACKUP_VARIABLE_EUR_MWH = _float_assumption("backup_variable_eur_mwh")

WIND_CAPACITY_EUR_MW_DAY = _float_assumption("wind_capacity_eur_mw_day")
SOLAR_PPA_CAPACITY_EUR_MW_DAY = _float_assumption("solar_ppa_capacity_eur_mw_day")
ONSITE_SOLAR_CAPACITY_EUR_MW_DAY = _float_assumption("onsite_solar_capacity_eur_mw_day")
BATTERY_POWER_EUR_MW_DAY = _float_assumption("battery_power_eur_mw_day")
BATTERY_ENERGY_EUR_MWH_DAY = _float_assumption("battery_energy_eur_mwh_day")
BACKUP_CAPACITY_EUR_MW_DAY = _float_assumption("backup_capacity_eur_mw_day")

DEFAULT_FRONTIER_POINTS = _int_assumption("frontier_points")

CapacityVar = Literal[
    "wind_capacity_mw",
    "solar_ppa_capacity_mw",
    "onsite_solar_capacity_mw",
    "battery_power_capacity_mw",
    "battery_energy_capacity_mwh",
    "backup_capacity_mw",
]
HourlyVar = Literal[
    "grid_mw",
    "wind_ppa_mw",
    "wind_curtail_mw",
    "solar_ppa_mw",
    "solar_ppa_curtail_mw",
    "onsite_solar_mw",
    "onsite_curtail_mw",
    "battery_charge_mw",
    "battery_discharge_mw",
    "battery_soc_mwh",
    "backup_mw",
]

CAPACITY_VARS: tuple[CapacityVar, ...] = (
    "wind_capacity_mw",
    "solar_ppa_capacity_mw",
    "onsite_solar_capacity_mw",
    "battery_power_capacity_mw",
    "battery_energy_capacity_mwh",
    "backup_capacity_mw",
)
HOURLY_VARS: tuple[HourlyVar, ...] = (
    "grid_mw",
    "wind_ppa_mw",
    "wind_curtail_mw",
    "solar_ppa_mw",
    "solar_ppa_curtail_mw",
    "onsite_solar_mw",
    "onsite_curtail_mw",
    "battery_charge_mw",
    "battery_discharge_mw",
    "battery_soc_mwh",
    "backup_mw",
)
