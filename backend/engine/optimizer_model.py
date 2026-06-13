"""Linear-program model for single-site supply optimization."""

import importlib
from dataclasses import dataclass
from typing import Any, cast

from backend.engine.assumptions import ASSUMPTIONS
from backend.engine.contracts import OptimizeRequest, SiteFeature
from backend.engine.optimizer_constants import (
    BACKUP_CAPACITY_EUR_MW_DAY,
    BACKUP_CARBON_G_KWH,
    BACKUP_VARIABLE_EUR_MWH,
    BATTERY_CHARGE_EFFICIENCY,
    BATTERY_DISCHARGE_EFFICIENCY,
    BATTERY_ENERGY_EUR_MWH_DAY,
    BATTERY_POWER_EUR_MW_DAY,
    CAPACITY_VARS,
    CURTAILMENT_PENALTY_EUR_MWH,
    GRID_IMPORT_MARGIN_EUR_MWH,
    HOURLY_VARS,
    HOURS_PER_DAY,
    ONSITE_SOLAR_CAPACITY_EUR_MW_DAY,
    ONSITE_SOLAR_VARIABLE_EUR_MWH,
    SOLAR_PPA_CAPACITY_EUR_MW_DAY,
    WIND_CAPACITY_EUR_MW_DAY,
    CapacityVar,
    HourlyVar,
)
from backend.engine.optimizer_profiles import (
    build_grid_price_profile,
    build_load_profile,
    build_solar_profile,
    build_wind_profile,
)


@dataclass(frozen=True)
class VariableIndex:
    """Index lookup for LP decision variables."""

    capacity: dict[CapacityVar, int]
    hourly: dict[tuple[HourlyVar, int], int]
    count: int


@dataclass(frozen=True)
class OptimizationInputs:
    """Site, request, and deterministic profile inputs to the LP."""

    site: SiteFeature
    request: OptimizeRequest
    load_mw: list[float]
    wind_cf: list[float]
    solar_cf: list[float]
    grid_price_eur_mwh: list[float]
    carbon_cap_g_kwh: float | None


@dataclass(frozen=True)
class OptimizationSolution:
    """Optimal decision-vector plus enough metadata to build response metrics."""

    inputs: OptimizationInputs
    variables: VariableIndex
    x: list[float]
    total_cost_eur: float
    solver_message: str

    def capacity(self, name: CapacityVar) -> float:
        """Return an optimized capacity decision variable."""

        return _positive(self.x[self.variables.capacity[name]])

    def hourly(self, name: HourlyVar, hour: int) -> float:
        """Return an optimized hourly decision variable."""

        return _positive(self.x[self.variables.hourly[(name, hour)]])


@dataclass(frozen=True)
class _LinprogResult:
    x: list[float]
    objective_value: float
    message: str


def build_inputs(
    site: SiteFeature,
    request: OptimizeRequest,
    carbon_cap_g_kwh: float | None,
) -> OptimizationInputs:
    """Build deterministic LP inputs for one site and request."""

    return OptimizationInputs(
        site=site,
        request=request,
        load_mw=build_load_profile(request.load_mw, request.load_profile),
        wind_cf=build_wind_profile(site.wind_cf),
        solar_cf=build_solar_profile(site.solar_cf),
        grid_price_eur_mwh=build_grid_price_profile(site),
        carbon_cap_g_kwh=carbon_cap_g_kwh,
    )


def solve_supply_lp(inputs: OptimizationInputs) -> OptimizationSolution:
    """Solve the single-site supply LP for one carbon cap."""

    variables = _build_variable_index()
    result = _linprog(
        _objective(inputs, variables),
        _bounds(inputs, variables),
        *_equalities(inputs, variables),
        *_inequalities(inputs, variables),
    )
    return OptimizationSolution(
        inputs=inputs,
        variables=variables,
        x=result.x,
        total_cost_eur=result.objective_value,
        solver_message=result.message,
    )


def _build_variable_index() -> VariableIndex:
    capacity: dict[CapacityVar, int] = {name: index for index, name in enumerate(CAPACITY_VARS)}
    offset = len(capacity)
    hourly: dict[tuple[HourlyVar, int], int] = {}
    for hour in range(HOURS_PER_DAY):
        for name in HOURLY_VARS:
            hourly[(name, hour)] = offset
            offset += 1
    return VariableIndex(capacity=capacity, hourly=hourly, count=offset)


def _objective(inputs: OptimizationInputs, variables: VariableIndex) -> list[float]:
    coefficients = [0.0 for _ in range(variables.count)]
    optimizer_assumptions = cast(dict[str, object], ASSUMPTIONS["optimizer"])
    wind_ppa_cost = _float_assumption(optimizer_assumptions, "wind_ppa_eur_mwh")
    solar_ppa_cost = _float_assumption(optimizer_assumptions, "solar_ppa_eur_mwh")

    capacity_costs: dict[CapacityVar, float] = {
        "wind_capacity_mw": WIND_CAPACITY_EUR_MW_DAY,
        "solar_ppa_capacity_mw": SOLAR_PPA_CAPACITY_EUR_MW_DAY,
        "onsite_solar_capacity_mw": ONSITE_SOLAR_CAPACITY_EUR_MW_DAY,
        "battery_power_capacity_mw": BATTERY_POWER_EUR_MW_DAY,
        "battery_energy_capacity_mwh": BATTERY_ENERGY_EUR_MWH_DAY,
        "backup_capacity_mw": BACKUP_CAPACITY_EUR_MW_DAY,
    }
    for name, cost in capacity_costs.items():
        coefficients[variables.capacity[name]] = cost

    for hour in range(HOURS_PER_DAY):
        coefficients[variables.hourly[("grid_mw", hour)]] = (
            inputs.grid_price_eur_mwh[hour] + GRID_IMPORT_MARGIN_EUR_MWH
        )
        coefficients[variables.hourly[("wind_ppa_mw", hour)]] = wind_ppa_cost
        coefficients[variables.hourly[("wind_curtail_mw", hour)]] = (
            wind_ppa_cost + CURTAILMENT_PENALTY_EUR_MWH
        )
        coefficients[variables.hourly[("solar_ppa_mw", hour)]] = solar_ppa_cost
        coefficients[variables.hourly[("solar_ppa_curtail_mw", hour)]] = (
            solar_ppa_cost + CURTAILMENT_PENALTY_EUR_MWH
        )
        coefficients[variables.hourly[("onsite_solar_mw", hour)]] = ONSITE_SOLAR_VARIABLE_EUR_MWH
        coefficients[variables.hourly[("onsite_curtail_mw", hour)]] = (
            ONSITE_SOLAR_VARIABLE_EUR_MWH + CURTAILMENT_PENALTY_EUR_MWH
        )
        coefficients[variables.hourly[("backup_mw", hour)]] = BACKUP_VARIABLE_EUR_MWH
    return coefficients


def _float_assumption(values: dict[str, object], key: str) -> float:
    value = values[key]
    if isinstance(value, int | float):
        return float(value)
    raise TypeError(f"Optimizer assumption {key} must be numeric.")


def _bounds(
    inputs: OptimizationInputs,
    variables: VariableIndex,
) -> list[tuple[float | None, float | None]]:
    peak_load = max(inputs.load_mw)
    site = inputs.site
    bounds: list[tuple[float | None, float | None]] = [(0.0, None) for _ in range(variables.count)]

    bounds[variables.capacity["wind_capacity_mw"]] = (0.0, peak_load * 4.0)
    bounds[variables.capacity["solar_ppa_capacity_mw"]] = (0.0, peak_load * 4.0)
    bounds[variables.capacity["onsite_solar_capacity_mw"]] = (
        0.0,
        peak_load * (0.35 + site.buildable_fraction),
    )
    bounds[variables.capacity["battery_power_capacity_mw"]] = (0.0, peak_load * 1.5)
    bounds[variables.capacity["battery_energy_capacity_mwh"]] = (0.0, peak_load * 10.0)
    bounds[variables.capacity["backup_capacity_mw"]] = (0.0, peak_load)

    for hour in range(HOURS_PER_DAY):
        bounds[variables.hourly[("grid_mw", hour)]] = (0.0, site.headroom_mw)

    return bounds


def _equalities(
    inputs: OptimizationInputs,
    variables: VariableIndex,
) -> tuple[list[list[float]], list[float]]:
    rows: list[list[float]] = []
    rhs: list[float] = []

    for hour in range(HOURS_PER_DAY):
        balance = _empty_row(variables)
        for name in (
            "grid_mw",
            "wind_ppa_mw",
            "solar_ppa_mw",
            "onsite_solar_mw",
            "battery_discharge_mw",
            "backup_mw",
        ):
            balance[variables.hourly[(cast(HourlyVar, name), hour)]] = 1.0
        balance[variables.hourly[("battery_charge_mw", hour)]] = -1.0
        rows.append(balance)
        rhs.append(inputs.load_mw[hour])

        rows.append(
            _resource_balance_row(
                variables,
                hour,
                "wind_ppa_mw",
                "wind_curtail_mw",
                "wind_capacity_mw",
                inputs.wind_cf[hour],
            )
        )
        rhs.append(0.0)

        rows.append(
            _resource_balance_row(
                variables,
                hour,
                "solar_ppa_mw",
                "solar_ppa_curtail_mw",
                "solar_ppa_capacity_mw",
                inputs.solar_cf[hour],
            )
        )
        rhs.append(0.0)

        rows.append(
            _resource_balance_row(
                variables,
                hour,
                "onsite_solar_mw",
                "onsite_curtail_mw",
                "onsite_solar_capacity_mw",
                inputs.solar_cf[hour],
            )
        )
        rhs.append(0.0)

        rows.append(_storage_transition_row(variables, hour))
        rhs.append(0.0)

    return rows, rhs


def _resource_balance_row(
    variables: VariableIndex,
    hour: int,
    dispatch_var: HourlyVar,
    curtailment_var: HourlyVar,
    capacity_var: CapacityVar,
    capacity_factor: float,
) -> list[float]:
    row = _empty_row(variables)
    row[variables.hourly[(dispatch_var, hour)]] = 1.0
    row[variables.hourly[(curtailment_var, hour)]] = 1.0
    row[variables.capacity[capacity_var]] = -capacity_factor
    return row


def _storage_transition_row(variables: VariableIndex, hour: int) -> list[float]:
    previous_hour = (hour - 1) % HOURS_PER_DAY
    row = _empty_row(variables)
    row[variables.hourly[("battery_soc_mwh", hour)]] = 1.0
    row[variables.hourly[("battery_soc_mwh", previous_hour)]] -= 1.0
    row[variables.hourly[("battery_charge_mw", hour)]] = -BATTERY_CHARGE_EFFICIENCY
    row[variables.hourly[("battery_discharge_mw", hour)]] = 1.0 / BATTERY_DISCHARGE_EFFICIENCY
    return row


def _inequalities(
    inputs: OptimizationInputs,
    variables: VariableIndex,
) -> tuple[list[list[float]], list[float]]:
    rows: list[list[float]] = []
    rhs: list[float] = []

    for hour in range(HOURS_PER_DAY):
        rows.append(
            _capacity_limit_row(
                variables,
                "battery_charge_mw",
                hour,
                "battery_power_capacity_mw",
            )
        )
        rhs.append(0.0)

        rows.append(
            _capacity_limit_row(
                variables,
                "battery_discharge_mw",
                hour,
                "battery_power_capacity_mw",
            )
        )
        rhs.append(0.0)

        rows.append(
            _capacity_limit_row(
                variables,
                "battery_soc_mwh",
                hour,
                "battery_energy_capacity_mwh",
            )
        )
        rhs.append(0.0)

        rows.append(_capacity_limit_row(variables, "backup_mw", hour, "backup_capacity_mw"))
        rhs.append(0.0)

    if inputs.carbon_cap_g_kwh is not None:
        carbon_row = _empty_row(variables)
        for hour in range(HOURS_PER_DAY):
            carbon_row[variables.hourly[("grid_mw", hour)]] = inputs.site.carbon_intensity_g_kwh
            carbon_row[variables.hourly[("backup_mw", hour)]] = BACKUP_CARBON_G_KWH
        rows.append(carbon_row)
        rhs.append(inputs.carbon_cap_g_kwh * sum(inputs.load_mw))

    return rows, rhs


def _capacity_limit_row(
    variables: VariableIndex,
    hourly_var: HourlyVar,
    hour: int,
    capacity_var: CapacityVar,
) -> list[float]:
    row = _empty_row(variables)
    row[variables.hourly[(hourly_var, hour)]] = 1.0
    row[variables.capacity[capacity_var]] = -1.0
    return row


def _empty_row(variables: VariableIndex) -> list[float]:
    return [0.0 for _ in range(variables.count)]


def _linprog(
    objective: list[float],
    bounds: list[tuple[float | None, float | None]],
    equalities: list[list[float]],
    equality_rhs: list[float],
    inequalities: list[list[float]],
    inequality_rhs: list[float],
) -> _LinprogResult:
    optimize_module = cast(Any, importlib.import_module("scipy.optimize"))
    result = optimize_module.linprog(
        c=objective,
        A_ub=inequalities,
        b_ub=inequality_rhs,
        A_eq=equalities,
        b_eq=equality_rhs,
        bounds=bounds,
        method="highs",
    )
    success = bool(result.success)
    if not success:
        message = str(result.message)
        raise RuntimeError(f"Supply optimizer did not find a feasible optimum: {message}")
    return _LinprogResult(
        x=[float(value) for value in result.x],
        objective_value=float(result.fun),
        message=str(result.message),
    )


def _positive(value: float) -> float:
    if abs(value) < 1e-7:
        return 0.0
    return max(0.0, value)
