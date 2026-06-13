from backend.engine.contracts import OptimizeRequest
from backend.engine.fixtures import get_site
from backend.engine.optimizer import optimize_supply_mix


def _demo_site():
    site = get_site("851f25d7fffffff")
    assert site is not None
    return site


def _high_carbon_site():
    site = get_site("851fa62bfffffff")
    assert site is not None
    return site


def _assert_hourly_energy_balance(row: dict[str, float]) -> None:
    supply = (
        row["grid_mw"]
        + row["wind_ppa_mw"]
        + row["solar_ppa_mw"]
        + row["onsite_solar_mw"]
        + row["battery_discharge_mw"]
        + row["backup_mw"]
    )
    demand = row["load_mw"] + row["battery_charge_mw"]
    assert abs(supply - demand) <= 0.05


def test_optimizer_returns_chart_ready_pareto_frontier_for_demo_site() -> None:
    response = optimize_supply_mix(
        _demo_site(),
        OptimizeRequest(cell_id="851f25d7fffffff", load_mw=280),
    )

    assert response.solver_status == "optimal"
    assert response.optimization_horizon_hours == 24
    assert 8 <= len(response.pareto_frontier) <= 12
    assert response.pareto_frontier[0].carbon_cap_g_kwh is None
    assert response.effective_cost_eur_mwh > 0
    assert 0 <= response.effective_carbon_g_kwh <= _demo_site().carbon_intensity_g_kwh
    assert 0 <= response.annual_matched_clean_share <= 1
    assert 0 <= response.hourly_24_7_cfe_share <= 1
    assert response.dispatch_preview
    assert response.dispatch_summary["total_load_mwh"] > 0
    assert response.dispatch_summary["total_curtailment_mwh"] >= 0

    for point in response.pareto_frontier:
        assert point.effective_cost_eur_mwh > 0
        assert point.effective_carbon_g_kwh >= 0
        assert 0 <= point.backup_share <= 1
        assert point.curtailment_share >= 0


def test_optimizer_enforces_hourly_energy_balance_and_storage_bounds() -> None:
    response = optimize_supply_mix(
        _demo_site(),
        OptimizeRequest(cell_id="851f25d7fffffff", load_mw=280, carbon_cap_g_kwh=30),
    )
    summary = response.dispatch_summary

    for row in response.dispatch_preview:
        _assert_hourly_energy_balance(row)
        assert 0 <= row["grid_mw"] <= _demo_site().headroom_mw
        assert 0 <= row["battery_charge_mw"] <= summary["battery_power_capacity_mw"] + 0.05
        assert 0 <= row["battery_discharge_mw"] <= summary["battery_power_capacity_mw"] + 0.05
        assert 0 <= row["battery_soc_mwh"] <= summary["battery_energy_capacity_mwh"] + 0.05

    assert (
        abs(
            response.dispatch_preview[0]["battery_soc_mwh"]
            - response.dispatch_preview[-1]["battery_soc_mwh"]
        )
        <= summary["battery_power_capacity_mw"] + 0.05
    )


def test_optimizer_respects_optional_carbon_cap() -> None:
    unconstrained = optimize_supply_mix(
        _high_carbon_site(),
        OptimizeRequest(cell_id="851fa62bfffffff", load_mw=280),
    )
    constrained = optimize_supply_mix(
        _high_carbon_site(),
        OptimizeRequest(cell_id="851fa62bfffffff", load_mw=280, carbon_cap_g_kwh=100),
    )

    assert constrained.effective_carbon_g_kwh <= 100.05
    assert constrained.effective_carbon_g_kwh <= unconstrained.effective_carbon_g_kwh
    assert constrained.effective_cost_eur_mwh >= unconstrained.effective_cost_eur_mwh


def test_optimizer_supports_spiky_training_load_profile() -> None:
    response = optimize_supply_mix(
        _demo_site(),
        OptimizeRequest(
            cell_id="851f25d7fffffff",
            load_mw=280,
            load_profile="spiky_training",
        ),
    )
    loads = {row["load_mw"] for row in response.dispatch_preview}

    assert response.load_profile == "spiky_training"
    assert len(loads) > 1
    for row in response.dispatch_preview:
        _assert_hourly_energy_balance(row)
