"""Deterministic-fixture supply-mix optimizer.

The Pareto frontier is *not* a real LP solve; it is a contract-shaped
fixture so the API can return a chart-ready response while the live
solver work proceeds out-of-band. Replace with a real solver behind
the same `optimize_supply_mix` signature when ready.
"""

from backend.engine.contracts import OptimizeRequest, ParetoPoint, SiteFeature, SupplyMixResponse


def _portfolio_for_site(site: SiteFeature) -> dict[str, float]:
    clean_bias = max(0.0, min(1.0, (500 - site.carbon_intensity_g_kwh) / 500))
    wind_share = round(0.18 + site.wind_cf * 0.35, 2)
    solar_share = round(0.06 + site.solar_cf * 0.35, 2)
    battery_share = 0.05 if site.price_volatility > 25 else 0.03
    grid_share = round(max(0.25, 1 - wind_share - solar_share - battery_share), 2)
    onsite_share = round(min(0.12, 0.04 + site.buildable_fraction * 0.08), 2)

    total = grid_share + wind_share + solar_share + onsite_share + battery_share
    return {
        "grid": round(grid_share / total, 3),
        "wind_ppa": round(wind_share / total, 3),
        "solar_ppa": round(solar_share / total, 3),
        "onsite_solar": round(onsite_share / total, 3),
        "battery_shifted": round(battery_share / total, 3),
        "clean_bias": round(clean_bias, 3),
    }


def optimize_supply_mix(site: SiteFeature, request: OptimizeRequest) -> SupplyMixResponse:
    """Return a deterministic fixture supply-mix response for the selected site."""

    portfolio = _portfolio_for_site(site)
    base_cost = (
        site.mean_price_eur_mwh * portfolio["grid"]
        + 55 * portfolio["wind_ppa"]
        + 45 * portfolio["solar_ppa"]
    )
    effective_cost = round(base_cost + 8 + site.price_volatility * 0.05, 2)
    clean_share = portfolio["wind_ppa"] + portfolio["solar_ppa"] + portfolio["onsite_solar"]
    effective_carbon = round(site.carbon_intensity_g_kwh * portfolio["grid"] * 0.92, 2)

    carbon_caps = [None, 250, 175, 100, 50]
    pareto: list[ParetoPoint] = []
    for idx, cap in enumerate(carbon_caps):
        reduction = idx * 0.11
        grid_share = max(0.22, portfolio["grid"] - reduction)
        added_clean = portfolio["grid"] - grid_share
        pareto.append(
            ParetoPoint(
                carbon_cap_g_kwh=cap,
                effective_cost_eur_mwh=round(effective_cost + idx * 6.5, 2),
                effective_carbon_g_kwh=round(max(18.0, effective_carbon - idx * 34), 2),
                grid_share=round(grid_share, 3),
                wind_ppa_share=round(portfolio["wind_ppa"] + added_clean * 0.55, 3),
                solar_ppa_share=round(portfolio["solar_ppa"] + added_clean * 0.30, 3),
                onsite_solar_share=round(portfolio["onsite_solar"] + added_clean * 0.10, 3),
                battery_shifted_share=round(portfolio["battery_shifted"] + added_clean * 0.05, 3),
            )
        )

    dispatch_preview: list[dict[str, float]] = []
    for hour in range(24):
        solar_shape = max(0.0, 1 - abs(hour - 13) / 7)
        wind_shape = 0.85 + (hour % 6) * 0.03
        dispatch_preview.append(
            {
                "hour": hour,
                "load_mw": request.load_mw,
                "grid_mw": round(request.load_mw * portfolio["grid"], 2),
                "wind_ppa_mw": round(request.load_mw * portfolio["wind_ppa"] * wind_shape, 2),
                "solar_mw": round(
                    request.load_mw
                    * (portfolio["solar_ppa"] + portfolio["onsite_solar"])
                    * solar_shape,
                    2,
                ),
                "battery_mw": round(
                    request.load_mw * portfolio["battery_shifted"] if hour in {19, 20, 21} else 0,
                    2,
                ),
            }
        )

    return SupplyMixResponse(
        cell_id=site.cell_id,
        load_mw=request.load_mw,
        load_profile=request.load_profile,
        recommended_portfolio={k: v for k, v in portfolio.items() if k != "clean_bias"},
        effective_cost_eur_mwh=effective_cost,
        effective_carbon_g_kwh=effective_carbon,
        annual_matched_clean_share=round(
            min(0.96, clean_share + portfolio["battery_shifted"] * 0.35),
            3,
        ),
        hourly_24_7_cfe_share=round(
            min(0.86, clean_share * 0.82 + portfolio["battery_shifted"] * 0.5),
            3,
        ),
        pareto_frontier=pareto,
        dispatch_preview=dispatch_preview,
    )
