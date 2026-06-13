"""Response and metric builders for the supply optimizer."""

from backend.engine.contracts import OptimizeRequest, ParetoPoint, SiteFeature, SupplyMixResponse
from backend.engine.optimizer_constants import BACKUP_CARBON_G_KWH, HOURS_PER_DAY, HourlyVar
from backend.engine.optimizer_model import OptimizationSolution


def build_supply_mix_response(
    site: SiteFeature,
    request: OptimizeRequest,
    recommended: OptimizationSolution,
    frontier: list[ParetoPoint],
) -> SupplyMixResponse:
    """Build the public API response from an optimized dispatch."""

    summary = dispatch_summary(recommended)
    return SupplyMixResponse(
        cell_id=site.cell_id,
        load_mw=request.load_mw,
        load_profile=request.load_profile,
        solver_status="optimal",
        optimization_horizon_hours=HOURS_PER_DAY,
        recommended_portfolio=portfolio(summary),
        effective_cost_eur_mwh=round_metric(effective_cost(recommended)),
        effective_carbon_g_kwh=round_metric(effective_carbon(recommended)),
        annual_matched_clean_share=round_metric(annual_clean_share(summary)),
        hourly_24_7_cfe_share=round_metric(hourly_clean_share(recommended)),
        pareto_frontier=frontier,
        dispatch_summary=summary,
        dispatch_preview=dispatch_preview(recommended),
    )


def build_pareto_point(
    carbon_cap_g_kwh: float | None,
    solution: OptimizationSolution,
) -> ParetoPoint:
    """Build one chart-ready Pareto frontier point."""

    summary = dispatch_summary(solution)
    return ParetoPoint(
        carbon_cap_g_kwh=carbon_cap_g_kwh,
        effective_cost_eur_mwh=round_metric(effective_cost(solution)),
        effective_carbon_g_kwh=round_metric(effective_carbon(solution)),
        grid_share=round_metric(summary["total_grid_mwh"] / summary["total_load_mwh"]),
        wind_ppa_share=round_metric(summary["total_wind_ppa_mwh"] / summary["total_load_mwh"]),
        solar_ppa_share=round_metric(summary["total_solar_ppa_mwh"] / summary["total_load_mwh"]),
        onsite_solar_share=round_metric(
            summary["total_onsite_solar_mwh"] / summary["total_load_mwh"]
        ),
        battery_shifted_share=round_metric(
            summary["total_battery_discharge_mwh"] / summary["total_load_mwh"]
        ),
        backup_share=round_metric(summary["total_backup_mwh"] / summary["total_load_mwh"]),
        curtailment_share=round_metric(
            summary["total_curtailment_mwh"] / summary["total_load_mwh"]
        ),
    )


def dispatch_summary(solution: OptimizationSolution) -> dict[str, float]:
    """Return aggregate dispatch, capacity, and grid-limit metrics."""

    totals = {
        "total_load_mwh": sum(solution.inputs.load_mw),
        "total_grid_mwh": total_hourly(solution, "grid_mw"),
        "total_wind_ppa_mwh": total_hourly(solution, "wind_ppa_mw"),
        "total_solar_ppa_mwh": total_hourly(solution, "solar_ppa_mw"),
        "total_onsite_solar_mwh": total_hourly(solution, "onsite_solar_mw"),
        "total_backup_mwh": total_hourly(solution, "backup_mw"),
        "total_battery_charge_mwh": total_hourly(solution, "battery_charge_mw"),
        "total_battery_discharge_mwh": total_hourly(solution, "battery_discharge_mw"),
        "total_curtailment_mwh": (
            total_hourly(solution, "wind_curtail_mw")
            + total_hourly(solution, "solar_ppa_curtail_mw")
            + total_hourly(solution, "onsite_curtail_mw")
        ),
        "wind_ppa_capacity_mw": solution.capacity("wind_capacity_mw"),
        "solar_ppa_capacity_mw": solution.capacity("solar_ppa_capacity_mw"),
        "onsite_solar_capacity_mw": solution.capacity("onsite_solar_capacity_mw"),
        "battery_power_capacity_mw": solution.capacity("battery_power_capacity_mw"),
        "battery_energy_capacity_mwh": solution.capacity("battery_energy_capacity_mwh"),
        "backup_capacity_mw": solution.capacity("backup_capacity_mw"),
        "grid_limit_mw": solution.inputs.site.headroom_mw,
    }
    return {key: round_metric(value) for key, value in totals.items()}


def total_hourly(solution: OptimizationSolution, name: HourlyVar) -> float:
    """Return the total MWh for one hourly dispatch variable."""

    return sum(solution.hourly(name, hour) for hour in range(HOURS_PER_DAY))


def portfolio(summary: dict[str, float]) -> dict[str, float]:
    """Return load-relative portfolio shares."""

    total_load = summary["total_load_mwh"]
    return {
        "grid": round_metric(summary["total_grid_mwh"] / total_load),
        "wind_ppa": round_metric(summary["total_wind_ppa_mwh"] / total_load),
        "solar_ppa": round_metric(summary["total_solar_ppa_mwh"] / total_load),
        "onsite_solar": round_metric(summary["total_onsite_solar_mwh"] / total_load),
        "battery_shifted": round_metric(summary["total_battery_discharge_mwh"] / total_load),
        "backup": round_metric(summary["total_backup_mwh"] / total_load),
        "curtailment": round_metric(summary["total_curtailment_mwh"] / total_load),
    }


def dispatch_preview(solution: OptimizationSolution) -> list[dict[str, float]]:
    """Return 24 hourly dispatch rows for charts and diagnostics."""

    rows: list[dict[str, float]] = []
    for hour in range(HOURS_PER_DAY):
        curtailment = (
            solution.hourly("wind_curtail_mw", hour)
            + solution.hourly("solar_ppa_curtail_mw", hour)
            + solution.hourly("onsite_curtail_mw", hour)
        )
        rows.append(
            {
                "hour": float(hour),
                "load_mw": round_metric(solution.inputs.load_mw[hour]),
                "grid_mw": round_metric(solution.hourly("grid_mw", hour)),
                "wind_ppa_mw": round_metric(solution.hourly("wind_ppa_mw", hour)),
                "solar_ppa_mw": round_metric(solution.hourly("solar_ppa_mw", hour)),
                "onsite_solar_mw": round_metric(solution.hourly("onsite_solar_mw", hour)),
                "battery_charge_mw": round_metric(solution.hourly("battery_charge_mw", hour)),
                "battery_discharge_mw": round_metric(solution.hourly("battery_discharge_mw", hour)),
                "battery_soc_mwh": round_metric(solution.hourly("battery_soc_mwh", hour)),
                "backup_mw": round_metric(solution.hourly("backup_mw", hour)),
                "curtailment_mw": round_metric(curtailment),
            }
        )
    return rows


def effective_cost(solution: OptimizationSolution) -> float:
    """Return effective daily cost per load MWh."""

    return solution.total_cost_eur / sum(solution.inputs.load_mw)


def effective_carbon(solution: OptimizationSolution) -> float:
    """Return load-weighted carbon intensity in gCO2e/kWh."""

    carbon = 0.0
    for hour in range(HOURS_PER_DAY):
        carbon += solution.hourly("grid_mw", hour) * solution.inputs.site.carbon_intensity_g_kwh
        carbon += solution.hourly("backup_mw", hour) * BACKUP_CARBON_G_KWH
    return carbon / sum(solution.inputs.load_mw)


def annual_clean_share(summary: dict[str, float]) -> float:
    """Return annual matched clean energy share from direct clean supply."""

    clean_mwh = (
        summary["total_wind_ppa_mwh"]
        + summary["total_solar_ppa_mwh"]
        + summary["total_onsite_solar_mwh"]
    )
    return min(1.0, clean_mwh / summary["total_load_mwh"])


def hourly_clean_share(solution: OptimizationSolution) -> float:
    """Return mean hourly 24/7 CFE share for the representative day."""

    hourly_shares: list[float] = []
    for hour in range(HOURS_PER_DAY):
        load = solution.inputs.load_mw[hour]
        clean_supply = (
            solution.hourly("wind_ppa_mw", hour)
            + solution.hourly("solar_ppa_mw", hour)
            + solution.hourly("onsite_solar_mw", hour)
            + solution.hourly("battery_discharge_mw", hour)
        )
        hourly_shares.append(min(1.0, clean_supply / load))
    return sum(hourly_shares) / len(hourly_shares)


def round_metric(value: float) -> float:
    """Round API metrics to stable precision."""

    return round(value, 4)


__all__ = [
    "annual_clean_share",
    "build_pareto_point",
    "build_supply_mix_response",
    "dispatch_preview",
    "dispatch_summary",
    "effective_carbon",
    "effective_cost",
    "hourly_clean_share",
    "portfolio",
    "round_metric",
    "total_hourly",
]
