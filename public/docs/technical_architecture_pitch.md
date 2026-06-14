# Loadstar Technical Architecture Pitch

This document is the technical talk track for explaining Loadstar clearly in a
pitch, demo, or judge Q&A. It focuses on what the system actually does today,
where every number comes from, what models are used, what parameters matter,
and how the matching/ranking/optimization logic works.

## 1. One-Minute Architecture Summary

Loadstar is a decision-support system for siting and powering AI data centers in
Europe. A user gives a target load in MW, a workload type, and priorities such as
cost, carbon, grid headroom, connectivity, or land. The system:

1. Converts the request into a typed `SearchRequest`.
2. Filters candidate H3 cells by feasibility: not excluded, enough grid
   headroom, and optional country filter.
3. Scores eligible cells with a transparent weighted model across price, carbon,
   congestion, grid distance, connectivity, land suitability, and ML viability.
4. Returns ranked sites with a per-factor explanation.
5. Runs a single-site linear program for the selected cell to produce a supply
   mix, dispatch preview, cost/carbon metrics, and a Pareto frontier.
6. Lets Fred, the agent layer, narrate the result using only engine-generated
   numbers.

The important point to say out loud:

> Loadstar is not a black-box recommendation. It is a transparent scoring engine
> plus an explainable ML layer plus a linear-program power optimizer, all exposed
> through typed FastAPI contracts and a React map interface.

## 2. Runtime System Shape

```text
Vite React SPA
  - MapLibre / deck.gl H3 overlays
  - ranked sites, detail drawer, optimizer charts, Fred chat
  - static fallback engine when API is unreachable

FastAPI API
  - /sites/search, /sites/{cell_id}, /sites/compare, /layers/{layer}
  - /optimize/supply-mix and async optimizer jobs
  - /agent/chat, /agent/explain, /agent/speech
  - /health, /assumptions, /meta/source-artifacts

Engine
  - Pydantic contracts in backend/engine/contracts.py
  - ranking in backend/engine/scoring.py
  - LP optimizer in backend/engine/optimizer_model.py

Pipeline
  - source access checks
  - subset ingestion
  - hourly price/carbon artifacts
  - AlphaEarth land model
  - LightGBM siting model
  - feature engineering and static layer assets

Storage and observability
  - committed reference JSON dataset
  - optional processed pipeline artifacts
  - source_artifacts SQLite ledger for data provenance
  - Postgres optimization_runs for async jobs
  - in-process LRU cache, optional Redis cache
  - request-id middleware and JSON logs
```

## 3. Spatial Unit and Candidate Dataset

The core spatial unit is an Uber H3 cell at resolution 5. H3 gives the product a
stable grid for search, map layers, feature joins, and API payloads.

Current committed reference dataset:

- File: `backend/engine/data/europe_sites.json`
- Frontend copy: `frontend/public/data/sites.json`
- Generation script: `scripts/build_europe_dataset.mjs`
- Count: 81 candidate cells
- Coverage: 30 European countries
- H3 resolution: 5

The dataset is generated deterministically from:

- curated European metros and known data-center markets,
- public country-level reference values for carbon intensity, wholesale price
  bands, and wind capacity factor,
- real internet-exchange coordinates for the IXP distance proxy,
- deterministic jitter so all values are stable but not visually identical.

The reference dataset is the full-continent fallback. When the subset pipeline
has produced `data/processed/subset/site_features_subset.json`, the repository
overlays those pipeline-derived rows onto matching `cell_id` values and keeps the
rest of the 81-cell base intact.

That gives the pitch a clean line:

> The map always has a complete European reference layer, and the cells touched
> by the real pipeline are upgraded with pipeline-derived prices, carbon, land,
> and model scores.

## 4. Data Sources and Current Status

| Data need | Intended/current source | Used for | Current implementation status |
|---|---|---|---|
| Candidate locations | Curated metro list in `scripts/build_europe_dataset.mjs` | The 81-cell reference dataset | Implemented and committed |
| Grid topology | PyPSA-Eur OSM network from Zenodo record `18619025` | substations, lines, topology, OPF-derived congestion/headroom | Access verified; raw `buses.csv`, `lines.csv`, `links.csv` exist under `data/raw/pypsa_eur/`; subset OPF artifact is still fixture-shaped |
| Wholesale prices | Ember hourly European wholesale price CSV/zip, ingested by `ember/ingest.py` | `mean_price_eur_mwh`, `price_volatility`, 24-hour price shape | Implemented when local `ember/dataset/ember_prices.db` exists; otherwise fixture price fallback |
| Carbon intensity | Preferred: ENTSO-E generation mix times technology emissions factors. Fallback: Ember-style monthly carbon broadcast | optimizer-ready hourly carbon and per-cell carbon | Preferred path implemented behind `--entsoe-generation-mix`; fallback is active when no input file is supplied |
| Congestion | Ember Grids for Data Centres plus OPF components | `congestion_index` and congestion map layer | Fixture hub/country records blended with OPF proxy until official Ember Grids records are loaded |
| Substations, water, exclusions, known data centers, IXPs | OpenStreetMap-derived records | grid distance, water distance, exclusion flag, known-DC labels, IXP proxy | Structured fallback records are generated from the reference dataset |
| Fiber/connectivity | ITU BBmaps preferred; IXP fallback | `dist_fiber_km`, `dist_ixp_km`, `latency_proxy_ms` | ITU page reachable, but extraction URL not configured; IXP/fiber proxy is active |
| Land suitability | Google AlphaEarth annual satellite embeddings through Earth Engine | `buildable_fraction`, `dc_similarity` | Earth Engine path implemented; current committed eval shows fixture land proxy because `EARTHENGINE_PROJECT` is not configured |
| Siting viability | LightGBM classifier preferred; transparent composite fallback | `lightgbm_score`, SHAP-like explanations | LightGBM path implemented; current committed eval shows transparent-composite fallback because local LightGBM runtime failed |

The source status is intentionally exposed through `/meta/source-artifacts`. The
system records artifact name, country scope, source status, checksum, record
count, fallback note, and generated time in `source_artifacts.db`.

## 5. Offline Data Pipeline

The pipeline is subset-first. The default development scope is:

```text
SE,DE,IE
```

Those countries support the core demo story:

- Sweden: clean, low-carbon Nordic candidate.
- Germany: Frankfurt-style connectivity and grid congestion comparison.
- Ireland: Dublin-style congestion and data-center pressure.

Pipeline commands are in the `Makefile`:

```bash
make pipeline-subset
make ingest-subset
make carbon-subset
make alphaearth-land-subset
make features-subset
make siting-model-subset
make layer-assets
```

The main artifact flow is:

```text
access_check
  -> public/docs/access_decisions.md

subset_ingestion
  -> pypsa_network_subset.json
  -> pypsa_clustered_opf.json
  -> hourly_energy_subset.json
  -> ember_grids_congestion_layers.json
  -> osm_site_feature_layers.json
  -> connectivity_fiber_or_ixp.json
  -> manifest.json

hourly_price
  -> hourly_price_subset.json

hourly_carbon
  -> hourly_carbon_subset.json

alphaearth_land
  -> alphaearth_land_subset.json
  -> eval/alphaearth_land_metrics.json

feature_engineering
  -> site_features_subset.json

siting_model
  -> siting_model_subset.json
  -> eval/siting_model_metrics.json

build_layer_assets
  -> frontend/public/layers/*.json
  -> frontend/public/data/sites.json
  -> frontend/public/data/assumptions.json
```

Every artifact writer goes through `backend/pipeline/artifacts.py`, which writes
stable JSON, computes SHA-256 checksums, and upserts metadata rows into the
SQLite source-artifact ledger.

## 6. Feature Engineering

The `SiteFeature` contract is the canonical feature surface. Each candidate
cell carries:

- identity: `cell_id`, country, region name, lat/lon, H3 resolution,
- economics: `mean_price_eur_mwh`, `price_volatility`,
- emissions: `carbon_intensity_g_kwh`,
- grid: `congestion_index`, `headroom_mw`, `dist_hv_substation_km`,
- connectivity: `dist_fiber_km`, `dist_ixp_km`, `latency_proxy_ms`,
- resources: `solar_cf`, `wind_cf`,
- physical feasibility: `water_dist_km`, `cooling_degree_proxy`,
  `buildable_fraction`, `exclusion_flag`,
- ML features: `dc_similarity`, `lightgbm_score`, `shap_values`.

Feature engineering blends upstream artifacts into a final per-cell record:

- Price: uses `hourly_price_subset.json` if present, otherwise keeps fixture
  price values.
- Carbon: averages hourly carbon values from `hourly_carbon_subset.json`.
- Congestion: blends three components:
  - 45% Ember hub/country congestion signal,
  - 35% OPF line-loading component,
  - 20% OPF nodal-price-spread component.
- Land: uses AlphaEarth output if present, otherwise fixture proxy.
- ML: uses siting-model output if present, otherwise the reference score.

Normalized score inputs use 5th/95th percentile clipping rather than raw min-max
scaling. This prevents one outlier cell from dominating the ranking.

## 7. Site Matching and Ranking Logic

The word "matching" means four things in this project.

### 7.1 Request-to-site matching

The first match is hard feasibility:

```text
eligible(site, request) =
    site.exclusion_flag == false
    and site.headroom_mw >= request.power_mw
    and site.country_code in request.country_filter, if supplied
```

That is what makes the requested MW size real. A 50 MW search and a 700 MW
search can return different site sets because headroom is a hard filter.

The engine also emits scale warnings:

- `<20 MW`: headroom rarely binds in this model.
- `>700 MW`: a single connection point is unrealistic; multi-connection campus
  planning is needed.

### 7.2 Preference matching

After feasibility, each candidate receives seven normalized factor scores:

| Factor | Raw fields | Direction |
|---|---|---|
| `price` | `mean_price_eur_mwh` | lower is better |
| `carbon` | `carbon_intensity_g_kwh` | lower is better |
| `congestion` | `congestion_index` | lower is better |
| `grid` | `dist_hv_substation_km` | lower is better |
| `connectivity` | average of fiber distance, IXP distance, latency proxy | lower is better |
| `land` | average of buildable fraction and data-center similarity | higher is better |
| `ml` | LightGBM or fallback viability score | higher is better |

Composite score:

```text
score(site) =
    price_score        * w_price
  + carbon_score       * w_carbon
  + congestion_score   * w_congestion
  + grid_score         * w_grid
  + connectivity_score * w_connectivity
  + land_score         * w_land
  + ml_score           * w_ml
```

Default weights:

| Weight | Value |
|---|---:|
| price | 0.18 |
| carbon | 0.24 |
| congestion | 0.18 |
| grid | 0.14 |
| connectivity | 0.10 |
| land | 0.08 |
| ml | 0.08 |

The default profile deliberately makes carbon and congestion visible for the
AI-training-campus story while still keeping cost and grid feasibility material.

Tie-break order:

1. Higher composite score.
2. Lower mean price.
3. Lexicographic `cell_id`.

### 7.3 Agent-to-engine matching

Fred maps natural language to engine parameters. For example:

- "cheapest" boosts `price`,
- "greenest" or "low carbon" boosts `carbon`,
- "headroom" or "biggest" boosts `grid`,
- "fiber" or "latency" boosts `connectivity`,
- country names become `country_filter`.

In both the LLM and deterministic fallback paths, emphasized factors are
multiplied by `3.0` and then renormalized into a valid weights object.

### 7.4 Clean-energy matching

The optimizer reports two clean-energy matching metrics:

- `annual_matched_clean_share`: total clean supply over total load.
- `hourly_24_7_cfe_share`: average hourly share of load matched by clean supply.

This distinction matters because annual matching can hide dirty hours; 24/7 CFE
is stricter and more credible for data-center power planning.

## 8. ML Models

### 8.1 AlphaEarth land model

Purpose:

- Estimate how much of a cell is buildable.
- Estimate how similar the cell is to land around known data-center sites.

Preferred model path:

- Source: `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`
- Year: 2024
- Embedding bands: 64 bands, named `A00` to `A63`
- Earth Engine classifier: `smileRandomForest`
- Trees: 80
- Seed: `20260612`
- Train fraction: 0.8
- H3 proxy buffer: 4500 meters around each candidate point
- Outputs:
  - `buildable_fraction`
  - `dc_similarity`

The model trains two random-forest regressors from the same AlphaEarth embedding
sample set:

- one for buildable land,
- one for data-center-like land similarity.

Fallback path:

- If `EARTHENGINE_PROJECT` is missing or Earth Engine fails, the pipeline emits
  `fixture_land_proxy`.
- The current committed metrics file shows this fallback path as active.

Pitch line:

> We use AlphaEarth as a geospatial foundation-model feature extractor. We do
> not train a satellite model from scratch; we train a small supervised layer on
> top of the embeddings to turn satellite context into buildability and
> data-center-similarity features.

### 8.2 Siting propensity model

Purpose:

- Estimate `lightgbm_score`: the probability-like viability signal for a cell.
- Provide SHAP-like feature contributions for explanations.

Preferred model:

- Library: LightGBM
- Objective: binary classification
- Metric: AUC
- Boosting rounds: 40
- Learning rate: 0.08
- `num_leaves`: 7
- `max_depth`: 3
- `min_data_in_leaf`: 1
- `min_data_in_bin`: 1
- `min_sum_hessian_in_leaf`: `1e-3`
- Deterministic seeds: `20260612`
- Deterministic mode: enabled
- Force column-wise training: enabled

Training labels:

- Positives:
  - curated known data-center cells,
  - OSM known-data-center proxy cells,
  - when OSM positives are absent, a data-center-similarity proxy threshold.
- Negatives:
  - deterministic non-excluded cell samples,
  - 3 negatives per positive.
- Split:
  - geography-based holdout country.

Feature columns:

```text
mean_price_eur_mwh
carbon_intensity_g_kwh
congestion_index
headroom_mw
dist_hv_substation_km
dist_fiber_km
dist_ixp_km
latency_proxy_ms
solar_cf
wind_cf
water_dist_km
cooling_degree_proxy
buildable_fraction
dc_similarity
```

Fallback model:

If LightGBM is unavailable or fails, the pipeline uses a transparent composite
with fixed weights:

| Feature | Weight |
|---|---:|
| dc_similarity | 0.17 |
| headroom_mw | 0.11 |
| buildable_fraction | 0.11 |
| carbon_intensity_g_kwh | 0.09 |
| mean_price_eur_mwh | 0.08 |
| congestion_index | 0.08 |
| dist_hv_substation_km | 0.08 |
| dist_fiber_km | 0.08 |
| wind_cf | 0.07 |
| dist_ixp_km | 0.05 |
| latency_proxy_ms | 0.05 |
| solar_cf | 0.05 |
| water_dist_km | 0.04 |
| cooling_degree_proxy | 0.04 |

Current committed eval status:

- `active_method`: `transparent_composite`
- `source_status`: `fallback`
- Scope: `SE,DE,IE`
- Positive labels: curated known data-center cells and OSM proxy cells
- Negative sampling ratio: 3 negatives per positive

Honest framing:

> The LightGBM path is implemented and tested, but the committed local run is on
> the transparent fallback. That is acceptable for a demo because the fallback is
> explainable and preserves the same API surface; installing the missing LightGBM
> runtime dependency switches the artifact back to the trained path.

## 9. Supply-Mix Optimizer

The optimizer answers:

> If I build this much load at this cell, how should I power it across grid
> import, PPAs, on-site solar, batteries, and backup under different carbon caps?

Implementation:

- Entry point: `backend/engine/optimizer.py`
- LP model: `backend/engine/optimizer_model.py`
- Solver: `scipy.optimize.linprog(method="highs")`
- Horizon: 24 representative hours
- Pareto points: 10 default frontier points
- Load profiles:
  - `flat_24_7`
  - `spiky_training`

Decision variables:

Capacity variables:

```text
wind_capacity_mw
solar_ppa_capacity_mw
onsite_solar_capacity_mw
battery_power_capacity_mw
battery_energy_capacity_mwh
backup_capacity_mw
```

Hourly variables, for every hour:

```text
grid_mw
wind_ppa_mw
wind_curtail_mw
solar_ppa_mw
solar_ppa_curtail_mw
onsite_solar_mw
onsite_curtail_mw
battery_charge_mw
battery_discharge_mw
battery_soc_mwh
backup_mw
```

Core constraints:

- Hourly energy balance:

```text
grid
+ wind_ppa
+ solar_ppa
+ onsite_solar
+ battery_discharge
+ backup
- battery_charge
= load
```

- Wind and solar dispatch plus curtailment must equal optimized capacity times
  that hour's capacity factor.
- Battery state of charge is cyclic across the representative day.
- Battery charge/discharge cannot exceed battery power capacity.
- Battery state of charge cannot exceed battery energy capacity.
- Backup dispatch cannot exceed backup capacity.
- Grid import cannot exceed `site.headroom_mw`.
- Optional carbon cap limits total grid and backup emissions over the day.

Capacity bounds:

| Variable | Upper bound |
|---|---:|
| wind PPA capacity | `peak_load * 4.0` |
| solar PPA capacity | `peak_load * 4.0` |
| on-site solar capacity | `peak_load * (0.35 + buildable_fraction)` |
| battery power | `peak_load * 1.5` |
| battery energy | `peak_load * 10.0` |
| backup capacity | `peak_load` |
| hourly grid import | `site.headroom_mw` |

Objective:

Minimize daily effective cost:

```text
capacity costs
+ hourly grid import cost
+ wind PPA energy cost
+ solar PPA energy cost
+ on-site solar variable cost
+ backup variable cost
+ curtailment penalty
```

Optimizer assumptions:

| Parameter | Value |
|---|---:|
| WACC | 7% |
| wind PPA strike | 55 EUR/MWh |
| solar PPA strike | 45 EUR/MWh |
| solar capex reference | 600 EUR/kW |
| battery capex reference | 250 EUR/kWh |
| gas backup capex reference | 800 EUR/kW |
| battery charge efficiency | 94% |
| battery discharge efficiency | 94% |
| backup carbon | 620 gCO2e/kWh |
| backup variable cost | 260 EUR/MWh |
| grid import margin | 1 EUR/MWh |
| on-site solar variable cost | 4 EUR/MWh |
| curtailment penalty | 0.05 EUR/MWh |
| wind capacity cost | 150 EUR/MW-day |
| solar PPA capacity cost | 145 EUR/MW-day |
| on-site solar capacity cost | 120 EUR/MW-day |
| battery power cost | 36 EUR/MW-day |
| battery energy cost | 10 EUR/MWh-day |
| backup capacity cost | 28 EUR/MW-day |

Pareto frontier:

- The first solve is unconstrained.
- Then the model sweeps carbon caps at:

```text
0.95, 0.85, 0.75, 0.65, 0.55, 0.45, 0.35, 0.28, 0.22
```

times the selected site's baseline grid carbon intensity.

Returned metrics:

- `recommended_portfolio`
- `effective_cost_eur_mwh`
- `effective_carbon_g_kwh`
- `annual_matched_clean_share`
- `hourly_24_7_cfe_share`
- `pareto_frontier`
- `dispatch_summary`
- `dispatch_preview`

Pitch line:

> The siting engine tells you where to build. The LP tells you how that site can
> be powered, and what the marginal cost of lower carbon looks like.

## 10. Fred, the Agent Layer

Fred is a thin agent layer over the deterministic engine. It does not own the
math.

Preferred path:

- Gemini API
- Default model setting: `gemini-3.1-pro-preview`
- Enabled only when `LOADSTAR_LLM_ENABLED=true` and `GEMINI_API_KEY` is set
- Tool loop max iterations: 2
- LLM timeout: 12 seconds
- Max output tokens: 400
- Tools:
  - `search_sites`
  - `explain_site`

Fallback path:

- Regex and keyword parser.
- Builds a real `SearchRequest`.
- Runs the same site engine.
- Returns deterministic narration.

The UI displays the response source:

- `gemini` for live model output,
- `template` for deterministic fallback.

This is the right demo posture:

> The LLM is an interface layer, not a source of truth. If it is configured, it
> chooses tools and writes the explanation. If it is not configured, the product
> still runs because the ranking and optimizer are deterministic.

Fred's speech endpoint uses ElevenLabs only when server-side credentials are
configured. The browser receives audio bytes; provider keys do not reach the
frontend.

## 11. API Surface

Main endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health` | process health, version, dependency status |
| `GET /assumptions` | public numeric assumptions |
| `GET /meta/source-artifacts` | data provenance, checksums, fallback status |
| `GET /layers/{layer_name}` | GeoJSON map layer |
| `POST /sites/search` | ranked candidate cells |
| `GET /sites/{cell_id}` | full site detail |
| `POST /sites/compare` | ordered site comparison |
| `POST /optimize/supply-mix` | synchronous LP result |
| `POST /optimize/supply-mix/async` | background optimizer job |
| `GET /optimize/jobs/{job_id}` | async job polling |
| `POST /agent/chat` | Fred chat and dashboard action |
| `POST /agent/explain` | selected-site explanation |
| `POST /agent/speech` | ElevenLabs text-to-speech proxy |

Every major request/response is a Pydantic model in
`backend/engine/contracts.py`, and frontend OpenAPI types can be regenerated
with:

```bash
make frontend-types
```

## 12. Frontend Architecture

The frontend is a Vite React 18 TypeScript SPA.

Key pieces:

- Map: MapLibre GL plus deck.gl H3-style overlays.
- Data fetching: TanStack Query.
- Charts: Recharts.
- State: Zustand.
- Chat rendering: React Markdown.
- Voice input: browser Web Speech API.
- Voice output: `/agent/speech` server-side ElevenLabs proxy.
- Static fallback: `frontend/src/lib/siteEngine.ts`.

The static fallback matters. On local development, the SPA uses the FastAPI
backend. In a static-only deployment, `/health` fails and the read path uses the
committed `frontend/public/data/sites.json` dataset plus a TypeScript port of
the Python scoring engine.

Parity is protected by a frontend golden test:

- It recomputes the composite-score layer in TypeScript.
- It compares it with the backend-generated static layer.
- This prevents the static SPA ranking from drifting away from the backend.

## 13. Caching, Jobs, and Observability

Caching:

- Sync optimizer results are deterministic and cached by request/site cache key.
- Default cache: in-process thread-safe LRU, max size 256.
- Optional cache: Redis when `REDIS_URL` is set.
- If Redis is unreachable, the factory falls back to LRU.

Async optimizer:

- `POST /optimize/supply-mix/async` inserts or reuses an `optimization_runs`
  row.
- FastAPI `BackgroundTasks` performs the solve.
- Job status transitions:

```text
pending -> running -> completed
pending -> running -> failed
```

Observability:

- `X-Request-ID` middleware accepts an inbound request id or generates a UUID.
- JSON logs include request id and event metadata.
- `/health` reports Postgres and Redis status.
- `/meta/source-artifacts` reports the active data version fingerprint.

## 14. How to Explain the Architecture in a Pitch

Use this sequence:

1. "We model Europe as H3 cells."
2. "Each cell is enriched with power, price, carbon, grid, connectivity, land,
   and ML features."
3. "The first decision is feasibility: enough headroom, not excluded, optional
   country filter."
4. "The second decision is preference matching: weighted, normalized factor
   scores."
5. "The ML model is not the whole answer; it is one factor in a transparent
   ranking."
6. "After choosing a site, the optimizer solves the power plan as a linear
   program."
7. "Fred is just the interface to the engine. The numbers come from tools, not
   from model memory."
8. "Every artifact records source status and checksum, so we can say what is
   live data and what is fallback."

Short version:

> Loadstar turns public grid, market, carbon, land, and connectivity signals
> into a per-cell feature table. It filters for feasible MW headroom, ranks the
> surviving cells with a transparent score plus an explainable siting model, and
> then solves a linear program to show how the chosen site can be powered under
> cost and carbon tradeoffs. The agent only narrates those engine outputs.

## 15. Technical Q&A Cheat Sheet

### Q1. How is Fred answering so fast?

The heavy work is not happening during the chat response. The backend already
has a local site feature table loaded from the committed reference dataset and
any available pipeline overlays. Fred either calls the local search/detail
services or, in fallback mode, builds the same request deterministically. The
LLM only narrates the returned facts. The optimizer is also fast because it is a
small 24-hour representative-day LP solved locally with SciPy HiGHS and cached
by request key.

### Q2. Is the LLM inventing site numbers?

No. The numbers come from engine and API tool outputs, not model memory. In the
live path, Fred uses Gemini tool calling with `search_sites` and `explain_site`.
In the deterministic path, it uses regex/keyword parsing and calls the same
search engine. The answer source is surfaced as `gemini` or `template`, but both
paths depend on the same site features and scoring code.

### Q3. Where does the site data come from?

The baseline comes from `backend/engine/data/europe_sites.json`, generated by
`scripts/build_europe_dataset.mjs`. It contains 81 H3 resolution-5 candidate
cells across 30 European countries. It is built from curated metro locations,
public country-level price/carbon/resource reference values, real IXP
coordinates, and deterministic transformations. When pipeline artifacts exist,
`site_features_subset.json` overlays upgraded values onto matching cells.

### Q4. Is this using live external APIs during the demo?

No, not for the normal demo path. The runtime reads local JSON, local processed
artifacts, optional local SQLite metadata, and optional Postgres job rows. Live
external calls are limited to optional integrations such as Gemini for narration
and ElevenLabs for speech. Energy data ingestion is designed as an offline
pipeline so the demo is stable and fast.

### Q5. Why use H3 cells?

H3 gives a stable spatial join key across the whole product. The same `cell_id`
links the map, ranking, site detail, pipeline artifacts, optimizer request, and
agent output. Resolution 5 is coarse enough for fast Europe-wide precomputation
and fine enough for a first-pass siting recommendation around specific metros.

### Q6. What exactly is being matched when I ask for a 200 MW site?

First, the request is matched against hard feasibility constraints. A site must
not be excluded, must have `headroom_mw >= 200`, and must pass any country
filter. Only after that does the scoring model rank the eligible sites by
weighted preferences like price, carbon, congestion, grid distance,
connectivity, land, and ML viability.

### Q7. How is the composite site score calculated?

Each factor is normalized to a 0..1 score using 5th/95th percentile clipping.
Lower is better for price, carbon, congestion, grid distance, fiber distance,
IXP distance, latency, water distance, and cooling proxy. Higher is better for
buildable land, data-center similarity, headroom, renewable capacity factors,
and ML viability. The final score is an additive weighted sum of the seven
search factors.

### Q8. What are the default weights?

The default weights are: price 0.18, carbon 0.24, congestion 0.18, grid 0.14,
connectivity 0.10, land 0.08, and ML 0.08. Carbon and congestion are slightly
heavier because the product is aimed at the data-center power constraint, not
only traditional fiber-led site selection.

### Q9. How does Fred translate phrases like "cheapest" or "greenest"?

Fred maps natural-language emphasis to scoring weights. "Cheapest" boosts the
price factor. "Greenest", "clean", or "low carbon" boosts carbon. "Headroom" or
"biggest" boosts grid. "Fiber" or "latency" boosts connectivity. The selected
factors are multiplied by 3.0 and then renormalized so the scoring contract
stays valid.

### Q10. What model is used for land suitability?

The preferred path uses Google AlphaEarth annual satellite embeddings from
`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`, year 2024. The pipeline samples 64
embedding bands and trains Earth Engine random-forest regressors with 80 trees
to output `buildable_fraction` and `dc_similarity`. If Earth Engine is not
configured, the artifact uses the fixture land proxy and marks that fallback in
metadata.

### Q11. What model is used for siting viability?

The preferred model is a LightGBM binary classifier trained on known
data-center cells versus deterministic negative samples. It uses feature columns
such as price, carbon, congestion, headroom, grid distance, connectivity,
renewable capacity factors, water, cooling, buildable land, and data-center
similarity. If LightGBM cannot run, the pipeline uses a transparent composite
fallback with the same feature surface.

### Q12. What are SHAP values doing here?

In the LightGBM path, SHAP-style contributions come from LightGBM prediction
contributions and explain which features pushed a cell's viability score. In
fallback mode, the pipeline emits transparent contribution values from the fixed
composite weights. Either way, the API surface still returns `shap_values` so
the explanation layer does not break.

### Q13. How do you avoid a black-box recommendation?

The final ranking is not only the ML score. ML is one factor with weight 0.08 by
default. The main score remains additive and inspectable: every result includes
factor scores, weights, weighted contributions, raw values, and whether lower or
higher is better. That makes the tradeoff visible instead of hiding it inside a
classifier.

### Q14. How does the optimizer decide the power mix?

For a selected cell, the optimizer builds a 24-hour representative-day linear
program. It chooses grid import, wind PPA capacity, solar PPA capacity, on-site
solar, battery power and energy, backup capacity, and hourly dispatch. It
minimizes daily effective cost while enforcing hourly energy balance, resource
availability, storage limits, grid headroom, backup limits, and optional carbon
caps.

### Q15. What does "under different carbon caps" mean?

The optimizer solves the LP multiple times. The first solve is unconstrained.
Then it sweeps carbon caps at 95%, 85%, 75%, 65%, 55%, 45%, 35%, 28%, and 22%
of the selected site's grid carbon intensity. The output is a Pareto frontier:
as carbon gets lower, cost and portfolio composition change.

### Q16. What is the difference between annual clean share and 24/7 CFE?

Annual matched clean share is total clean energy divided by total load over the
period. It can look good even if some hours are dirty. The 24/7 CFE metric is
stricter because it checks how much load is matched by clean supply hour by
hour, then averages those hourly shares.

### Q17. Why is Malmo showing low carbon so quickly?

For a site like Malmo, the displayed carbon value comes from the local
`SiteFeature` row. In the committed reference dataset, Swedish cells use a low
country-level carbon reference value. If the processed pipeline overlay exists,
the feature can be upgraded from `hourly_carbon_subset.json`; otherwise it stays
at the committed reference value. The quick response is a local lookup, not a
live carbon API call.

### Q18. How do you know which data is real and which is fallback?

Every pipeline CLI writes metadata through `backend/pipeline/artifacts.py`.
That metadata includes source status, artifact version, checksum, record count,
fallback note, generated time, and country scope. The API exposes it through
`GET /meta/source-artifacts`, and the markdown decision record lives in
`public/docs/access_decisions.md`.

### Q19. What happens if Gemini, ElevenLabs, Redis, or Postgres is unavailable?

Gemini is optional; Fred falls back to deterministic parsing and templates.
ElevenLabs is optional; speech returns a configuration/provider error while the
text UI still works. Redis is optional; the cache factory falls back to the
in-process LRU. Postgres is needed for async optimizer job persistence, but the
sync optimizer can still run through the local engine path.

### Q20. What is the strongest technical claim to make in Q&A?

Say that Loadstar separates the math from the narration. The ranking and
optimizer are deterministic, typed, test-covered engine paths. The LLM is only
an interaction layer that calls those paths and explains their outputs. Source
availability is also separated from runtime behavior through artifact overlays,
checksums, and explicit fallback metadata.

## 16. Current Limitations to Say Honestly

These are not failures; they are the boundary between the current demo and a
production data product.

- The committed 81-cell dataset is a reference dataset, not a live Europe-wide
  feed.
- Ember hourly price ingestion is implemented through a local CSV/SQLite path,
  but prices fall back to committed reference values if the local DB is absent.
- Current price data is country-level; multi-zone pricing such as SE1-SE4 is a
  known next improvement.
- Earth Engine / AlphaEarth is implemented but currently falls back without
  `EARTHENGINE_PROJECT`.
- ITU BBmaps is the preferred fiber source, but extraction is not yet configured;
  IXP/fiber proxy values are used meanwhile.
- PyPSA-Eur raw access is verified, but the subset OPF artifact is currently a
  precomputed fixture/proxy rather than a live PyPSA solve.
- The optimizer uses a 24-hour representative day, not an 8760-hour full-year
  solve.
- The committed siting-model eval is on the transparent composite fallback; the
  LightGBM path is implemented and tested but needs the local runtime dependency
  to train in this environment.

Best judge answer:

> We separated the architecture from source availability. The contracts,
> feature table, scoring, optimizer, provenance ledger, and fallbacks are all in
> place. When a source becomes available, it replaces a specific artifact without
> changing the API or frontend.
