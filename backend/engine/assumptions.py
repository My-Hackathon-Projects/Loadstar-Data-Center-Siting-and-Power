"""Numeric assumption tables shared by scoring, optimizer, and the API.

Update `ASSUMPTIONS.md` whenever the values here change.
"""

from typing import Any

DEFAULT_WEIGHTS = {
    "price": 0.18,
    "carbon": 0.24,
    "congestion": 0.18,
    "grid": 0.14,
    "connectivity": 0.10,
    "land": 0.08,
    "ml": 0.08,
}

ASSUMPTIONS: dict[str, Any] = {
    "scope": {
        "region": "Europe",
        "served_coverage": "Major European markets across 30 countries",
        "pipeline_development_countries": ["SE", "DE", "IE"],
        "data_mode": "reference_dataset",
    },
    "load": {
        "default_workload_type": "training",
        "default_profile": "flat_24_7",
        "default_pue": 1.2,
        "stretch_profile": "synthetic_spiky_training",
    },
    "scale_bands": {
        "small_mw_threshold": 20,
        "large_mw_threshold": 700,
        "small_warning": "Below roughly 20 MW, headroom rarely binds in this model.",
        "large_warning": (
            "Above roughly 700 MW, a single connection point is unrealistic; "
            "use multi-connection campus planning."
        ),
    },
    "scoring_weights": DEFAULT_WEIGHTS,
    "scoring_normalization": {
        "method": "percentile_clipping",
        "lower_percentile": 5,
        "upper_percentile": 95,
        "missing_value_score": 0,
        "degenerate_range_score": 1,
    },
    "optimizer": {
        "wacc": 0.07,
        "solar_capex_eur_kw": 600,
        "battery_capex_eur_kwh": 250,
        "gas_backup_capex_eur_kw": 800,
        "wind_ppa_eur_mwh": 55,
        "solar_ppa_eur_mwh": 45,
        "optimization_horizon_hours": 24,
        "frontier_points": 10,
        "battery_charge_efficiency": 0.94,
        "battery_discharge_efficiency": 0.94,
        "backup_carbon_g_kwh": 620,
        "backup_variable_eur_mwh": 260,
        "grid_import_margin_eur_mwh": 1,
        "onsite_solar_variable_eur_mwh": 4,
        "curtailment_penalty_eur_mwh": 0.05,
        "wind_capacity_eur_mw_day": 150,
        "solar_ppa_capacity_eur_mw_day": 145,
        "onsite_solar_capacity_eur_mw_day": 120,
        "battery_power_eur_mw_day": 36,
        "battery_energy_eur_mwh_day": 10,
        "backup_capacity_eur_mw_day": 28,
    },
}
