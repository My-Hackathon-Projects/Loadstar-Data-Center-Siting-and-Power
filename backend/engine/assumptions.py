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
        "development_countries": ["SE", "DE", "IE"],
        "data_mode": "fixture",
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
    "optimizer": {
        "wacc": 0.07,
        "solar_capex_eur_kw": 600,
        "battery_capex_eur_kwh": 250,
        "gas_backup_capex_eur_kw": 800,
        "wind_ppa_eur_mwh": 55,
        "solar_ppa_eur_mwh": 45,
    },
}
