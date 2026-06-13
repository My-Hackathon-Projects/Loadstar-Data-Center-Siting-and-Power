# Loadstar Assumptions

This file is the single source for numeric assumptions used by the skeleton, later optimizer work, and the agent-facing assumptions panel.

## Scope

| Assumption | Value | Source | Justification |
|---|---:|---|---|
| Region scope | Europe | Challenge brief and `public/docs/invertix_datacenter_siting_system_design.md` | All official pointer sources are strongest for Europe, especially PyPSA-Eur and Ember. |
| Development subset | `SE,DE,IE` | `public/docs/plan.md` | Covers the 280 MW demo: Nordic clean-power candidate, Frankfurt comparison, and Dublin congestion context. |
| Default workload | AI training | Challenge scenario and design doc | Training is latency-tolerant, so power/carbon trade-offs can dominate connectivity. |
| Default load profile | Flat 24/7 | IEA Energy and AI context in design doc | Standard first-order simplification for data-center planning. |
| Stretch load profile | Synthetic spiky training load | Design doc | Makes battery value visible beyond price arbitrage; not part of issue 1-5 skeleton. |
| Default PUE | `1.2` | IEA Energy and AI assumptions cited in design doc | Representative modern hyperscale assumption for first demo calculations. |

## Search Scale Bands

| Threshold | Behavior | Source | Justification |
|---|---|---|---|
| `<20 MW` | Warn that headroom rarely binds and rankings are mostly price/carbon/connectivity driven. | Design review feedback captured in `public/docs/plan.md` | Small facilities are unlikely to stress transmission-level connection headroom in this model. |
| `>700 MW` | Warn that a single connection point is unrealistic and multi-connection campus planning is needed. | Design review feedback captured in `public/docs/plan.md` | Very large campuses usually require multiple interconnection points and staged grid planning. |

## Scoring Defaults

| Assumption | Value | Source | Justification |
|---|---:|---|---|
| Price weight | `0.18` | Design doc composite score | Cost is material but should not dominate a carbon-heavy training demo. |
| Carbon weight | `0.24` | Design doc composite score | The first demo prioritizes clean energy. |
| Congestion weight | `0.18` | Challenge brief | Grid congestion is one of the official trade-off axes. |
| Grid proximity/headroom weight | `0.14` | Challenge brief and PyPSA-Eur pointer | Physical connection feasibility must remain visible. |
| Connectivity weight | `0.10` | ITU BBmaps pointer | Important, but less dominant for AI training workloads than inference. |
| Land suitability weight | `0.08` | AlphaEarth plan | Keeps land feasibility in the transparent score. |
| ML viability weight | `0.08` | LightGBM siting plan | Preserves model signal without hiding explicit trade-offs. |
| Search score normalization | 5th/95th percentile clipping | Issue 14 refactor | Keeps live search scoring aligned with feature-engineering artifacts and limits outlier dominance. |
| Missing score input | `0` | Issue 14 refactor | Missing or non-finite values should not inflate a candidate score. |
| Degenerate score range | `1` | Issue 14 refactor | If all eligible candidates tie on a field, that field should not penalize any candidate. |

## Optimizer Defaults

| Assumption | Value | Source | Justification |
|---|---:|---|---|
| WACC | `7%` | Design doc | Standard placeholder for annualized cost comparisons in the hackathon model. |
| Solar capex | `600 EUR/kW` | Design doc | Round-number planning assumption for first Pareto calculations. |
| Battery capex | `250 EUR/kWh` | Design doc | Round-number planning assumption for first Pareto calculations. |
| Gas backup capex | `800 EUR/kW` | Design doc | Optional firmness placeholder; not active in issue 1-5 skeleton. |
| Wind PPA strike | `55 EUR/MWh` | Hackathon modeling assumption | Plausible fixed strike for early comparative planning; replace with sourced values later. |
| Solar PPA strike | `45 EUR/MWh` | Hackathon modeling assumption | Plausible fixed strike for early comparative planning; replace with sourced values later. |
| Optimization horizon | `24` representative hours | Issue 12 implementation | Keeps the demo path interactive while preserving hourly balance and storage constraints. |
| Carbon cap sweep | `10` points including an unconstrained solve | Issue 12 implementation | Produces an 8-12 point cost/carbon Pareto frontier for one selected site. |
| Battery round-trip model | `94%` charge efficiency and `94%` discharge efficiency | Issue 12 implementation | Simple deterministic storage physics for the representative-day LP. |
| Backup emissions | `620 gCO2e/kWh` | Issue 12 implementation | Conservative optional backup emissions placeholder until generator-specific data is ingested. |
| Backup variable cost | `260 EUR/MWh` | Issue 12 implementation | Keeps backup available for feasibility without making it attractive against grid or clean supply. |
| Grid import margin | `1 EUR/MWh` | Issue 12 implementation | Represents small delivery/imbalance costs on top of fixture market prices. |
| On-site solar variable cost | `4 EUR/MWh` | Issue 12 implementation | Small operating-cost placeholder for direct on-site production. |
| Curtailment penalty | `0.05 EUR/MWh` | Issue 12 implementation | Breaks ties toward useful generation while keeping curtailment available. |
| Daily capacity costs | wind `150 EUR/MW-day`, solar PPA `145 EUR/MW-day`, on-site solar `120 EUR/MW-day`, battery power `36 EUR/MW-day`, battery energy `10 EUR/MWh-day`, backup `28 EUR/MW-day` | Issue 12 implementation | Converts planning cost signals into LP coefficients for the representative-day demo. |

## Hourly Carbon

| Method | Status | Source | Justification |
|---|---|---|---|
| ENTSO-E hourly generation mix times standard emissions factors | Preferred, implemented when `--entsoe-generation-mix` is supplied to `backend.pipeline.hourly_carbon` | `public/docs/plan.md`; artifact version `hourly-carbon-v1` | Produces optimizer-ready hourly carbon values and supports 24/7 CFE. |
| Repeat Ember monthly carbon intensity over each month’s hours | Active local fallback for `SE,DE,IE` when ENTSO-E input is unavailable | `public/docs/plan.md`; source version `ember-monthly-carbon-fixture-v1` | Keeps the optimizer usable if hourly generation mix access is delayed. |

Technology emissions factors for the preferred ENTSO-E method are stored in each `hourly_carbon_subset.json` artifact. Current defaults in `backend.pipeline.hourly_carbon` are: biomass `230`, coal `820`, gas `490`, geothermal `38`, hydro `24`, nuclear `12`, oil `650`, other `500`, other fossil `700`, other renewable `40`, solar `45`, and wind `11` gCO2e/kWh.

## Feature Engineering

| Assumption | Value | Source | Justification |
|---|---:|---|---|
| Feature artifact version | `site-features-v1` | Issue 8 implementation | Keeps map/API-facing feature rows versioned and checksum tracked. |
| Normalization method | 5th/95th percentile clipping | Issue 8 implementation | Reduces outlier dominance while keeping values interpretable for map overlays. |
| Congestion blend: Ember hub/country | `45%` | Issue 8 implementation | Keeps official congestion layer signal as the largest component. |
| Congestion blend: OPF line loading | `35%` | Issue 8 implementation | Adds local grid stress from the precomputed OPF artifact. |
| Congestion blend: nodal price spread | `20%` | Issue 8 implementation | Adds economic congestion signal without overwhelming hub/country context. |

## LP Solver

| Knob | Value | Source | Notes |
|---|---|---|---|
| Solver | `scipy.optimize.linprog(method="highs")` | `backend/engine/optimizer_model.py` | High-performance interior-point HiGHS implementation; deterministic given the seed. |
| Decision variables | ~270 | 6 capacity + 11 hourly × 24 hours | Capacity vars: wind, solar PPA, onsite solar, battery power/energy, backup. |
| Constraints | ~217 | 121 equality + 96 inequality | Energy balance, resource availability, battery dynamics, optional carbon cap. |
| Solves per request | up to 11 | Issue 12 implementation | 1 recommended portfolio + up to 10 Pareto frontier points. |
| Optimization horizon | 24 hours | `engine.assumptions.ASSUMPTIONS["optimizer"]` | Representative day; the full-year solve is out of scope for the demo. |

## Deterministic Seed

| Knob | Value | Source | Notes |
|---|---|---|---|
| Pipeline seed | `20260612` | `backend/pipeline/constants.py::DETERMINISTIC_SEED` | Anchor date in YYYYMMDD form. Used for every random sample, train/holdout split, and synthetic-record generator across the pipeline. |

## ML and External-Source Fallbacks

- **AlphaEarth (Issue 9):** when `EARTHENGINE_PROJECT` is unset or the
  Earth Engine sample fails, the pipeline emits a fixture-shaped land proxy.
  `eval/alphaearth_land_metrics.json` records `source_status: "fallback"` and
  the held-out metrics are placeholders (n=4 by construction).
- **LightGBM siting model (Issue 10):** when `lightgbm` or `numpy` are
  unavailable or training fails, the pipeline uses a transparent-composite
  scorer with the same feature surface. `siting_model_subset.json` carries
  `fallback: true` and `active_method: "transparent_composite"`.
- **Ember hourly carbon:** preferred path is ENTSO-E generation mix ×
  emissions factors when an ENTSO-E JSON file is provided to
  `make carbon-subset`. Fallback is the Ember monthly carbon broadcast
  (`active_method: "ember_monthly_repeat"`).
- **OpenAI explanation:** `/agent/explain` calls the OpenAI Responses API
  when `LOADSTAR_LLM_ENABLED=true` and `OPENAI_API_KEY` is set. On any
  error (auth, rate-limit, network, empty response) the endpoint falls back
  to a deterministic template that uses the same site facts. The
  `ExplainResponse.source` field surfaces which path produced the message.

## Source Fallback Implications

The current machine cannot fully verify private or credentialed sources without user-provided access. See `public/docs/access_decisions.md` for the latest status.

- If ITU BBmaps is blocked, issue 6 should ingest IXP distances instead and issue 8 should label the feature as an IXP/connectivity proxy rather than fiber distance.
- If Earth Engine or AlphaEarth approval stalls, issues 9 and 10 should omit AlphaEarth-derived fields and rely on transparent scoring plus non-embedding features.
- If Ember hourly prices are blocked, issue 6 should use a checked fixture or ENTSO-E-backed fallback and mark price values as provisional.
- If Zenodo is blocked, issue 6 cannot produce the PyPSA-Eur OPF artifact and must use fixture headroom/congestion until access is restored.
