# Loadstar Build Plan

## Summary

Loadstar is the product for the Invertix dedicated challenge, **Data-Center Siting & Power**. It helps a user decide where to build a data center in Europe and how to power it.

The product must:

- Recommend European data-center locations for a requested MW size.
- Explain trade-offs across price, carbon, grid headroom, congestion, connectivity, and land suitability.
- Show map overlays for capacity/headroom, prices, carbon, congestion, connectivity, exclusions, and composite score.
- Optimize a selected site's power supply mix across grid, PPA, on-site generation, storage, and optional backup.
- Provide a grounded chat agent whose numeric answers come only from backend tools.

Primary execution rule: whenever the next task is unclear, build whatever the **280 MW AI training campus demo path** needs next.

Primary demo path:

1. User enters a 280 MW AI training campus with carbon-heavy preferences.
2. The map highlights candidate sites in Europe.
3. The system compares a Nordic candidate against Frankfurt.
4. The optimizer returns a cost/carbon Pareto frontier and dispatch summary.
5. The agent explains the result using only backend tool output.

## Task Zero: Prove External Access Before Code

Before writing application code beyond this plan and access-check tooling, verify every external dependency with a trivial pull and record the result.

Required checks:

- **Google Earth Engine / AlphaEarth:** confirm project approval and run one tiny embedding sample or export.
- **Ember API:** confirm API key or public API access and pull one price/carbon response.
- **ITU BBmaps:** confirm the extraction path and query one fiber node/line sample or WMS metadata response.
- **Zenodo PyPSA-Eur:** confirm download access for Zenodo record `18619025` and inspect one network artifact.

If a check fails:

- Record the failure.
- Record the fallback.
- Do not block the walking skeleton.
- Use fixture data or a simplified proxy while access is resolved.

## Time Dimension And Execution Strategy

Use three execution lanes.

### 1. Walking Skeleton First

Build a thin end-to-end slice before completing any phase:

- Use a handful of H3 cells with fixture or partially fake features.
- Render them on the map.
- Search them through FastAPI.
- Open a site detail drawer.
- Run one optimizer call that returns a chart-ready response.

This exposes integration problems between PostGIS, FastAPI, deck.gl or map rendering, and the LP early.

### 2. Subset Pipeline Before Full Europe

Every pipeline command must support a country subset flag.

Default development subset:

```text
SE,DE,IE
```

These countries cover the main demo:

- Sweden: clean-power Nordic candidate.
- Germany: Frankfurt connectivity and congestion comparison.
- Ireland: Dublin congestion and moratorium context.

Run full Europe only after the subset pipeline is correct.

### 3. Full Product After Demo Path Works

Expand in this order:

1. Fixture walking skeleton.
2. Subset data for `SE,DE,IE`.
3. Full Europe data.
4. Hardening and scale improvements.

Cut order if time collapses:

1. Cut RAG / `lookup_context` first.
2. Cut LightGBM and use transparent composite scoring only.
3. Cut battery and flexible load from the optimizer.
4. Do not cut map overlays.
5. Do not cut the Pareto chart.
6. Do not cut site comparison.

## Core Stack And Models

- **Frontend:** Next.js + React + MapLibre GL + deck.gl H3 layer for the final product. The walking skeleton may start with a static web page using the same API contracts.
- **Backend:** FastAPI + Pydantic + SQLAlchemy.
- **Database:** PostgreSQL + PostGIS for production; Parquet/NetCDF for offline artifacts; Redis and worker queue only after the demo path works.
- **Spatial unit:** H3 resolution 5 for Europe-wide search; optional resolution 7 for shortlisted regions.
- **Land model:** AlphaEarth 64-dimensional embeddings plus Earth Engine Random Forest for `buildable_fraction`.
- **Siting model:** LightGBM binary classifier trained on known data-center cells vs sampled negatives; SHAP for explanations.
- **Optimizer:** PyPSA or linopy linear program solved with HiGHS.
- **Agent:** provider-configurable tool-calling LLM. Verify current model identifiers at build time. Do not hardcode a stale model string.

## Database And API Interfaces

### Database Tables

- `h3_cells`: `cell_id`, `geom`, `centroid`, `country_code`, `region_name`, `resolution`.
- `site_features`: price, carbon, congestion, headroom, substation distance, fiber distance, IXP distance, latency proxy, renewable capacity factors, water distance, cooling proxy, buildable fraction, AlphaEarth similarity, LightGBM score, SHAP JSON, and exclusion flags.
- `hourly_energy`: `zone_id`, `timestamp`, `price_eur_mwh`, `carbon_g_kwh`, `solar_cf`, `wind_cf`.
- `grid_nodes`: PyPSA/OSM node metadata, voltage, capacity/headroom proxy, nearest H3 cell.
- `grid_opf_results`: line loadings, nodal prices, nodal congestion metrics, solved artifact version.
- `fiber_assets`: ITU BBmaps nodes/lines and derived distance features.
- `congestion_layers`: Ember Grids hub/country congestion signals, queue pressure notes, moratorium flags, and citations.
- `known_data_centers`: OSM and curated positive labels with source and confidence.
- `model_runs`: model type, training data version, metrics, artifact path, created timestamp.
- `optimization_runs`: input site/load/constraints, result JSON, Pareto JSON, dispatch artifact path, cache key.
- `source_artifacts`: source name, license, retrieval date, raw path, processed path, checksum.

### Backend Endpoints

- `GET /health`
- `GET /layers/{layer_name}`
- `POST /sites/search`
- `GET /sites/{cell_id}`
- `POST /sites/compare`
- `POST /optimize/supply-mix`
- `POST /chat`
- `GET /assumptions`

### Search Validation

- Require `power_mw > 0`.
- Warn below roughly `20 MW` that headroom rarely binds.
- Warn above roughly `700 MW` that single-connection siting is unrealistic and needs multi-connection campus planning.
- The agent must repeat these warnings when relevant.

## Step-By-Step Build Tasks

### 1. Write This Plan

- Add `public/docs/plan.md`.
- Treat it as the source for later GitHub issue creation.
- Do not push; the user will commit and push.

Done when this file exists and matches the accepted execution strategy.

### 2. Run Task-Zero Access Checks

- Verify Earth Engine, Ember, ITU BBmaps, and Zenodo with trivial pulls.
- Record status, exact command or script used, result, and fallback.
- Use fixture data if any external source is unavailable.

Done when each external dependency is marked `ok`, `blocked`, or `fallback`.

### 3. Create Walking Skeleton

- Add minimal `web/`, `api/`, `engine/`, `pipeline/`, `ml/`, `eval/`, and `data/` structure.
- Seed 10 to 20 fixture H3 cells for Sweden, Germany, and Ireland.
- Render cells on a map-like UI.
- Search through the API.
- Open a site detail drawer.
- Return one chart-shaped optimizer response.

Done when the 280 MW demo path works against fixture data.

### 4. Define Assumptions

- Europe is v1 scope.
- Default workload is AI training.
- Default load profile is flat 24/7.
- Default PUE is `1.2`.
- Add optional stretch load profile: synthetic spiky training load.
- Document WACC, capex, PPA strike prices, emissions factors, carbon fallback method, and scale-band warnings.

Done when `ASSUMPTIONS.md` contains all numeric assumptions used by scoring and optimization.

### 5. Implement Minimal Database Schema

- Start with `h3_cells`, `site_features`, `hourly_energy`, and `optimization_runs`.
- Add remaining tables once the demo data flow is stable.
- Keep the first migration small.

Done when migrations can create a fresh demo database.

### 6. Build Subset-First Ingestion Pipeline

- Every ingestion command accepts `--countries SE,DE,IE`.
- Ingest PyPSA-Eur network.
- Solve clustered OPF once before the event; save line loadings and nodal prices.
- Never solve PyPSA-Eur live during the demo.
- Ingest Ember prices and carbon.
- Ingest Ember Grids for Data Centres into structured congestion layers.
- Ingest OSM substations, data centers, water, exclusions, and IXPs.
- Ingest ITU BBmaps fiber data or activate fallback.

Done when each official pointer source has a processed subset artifact or documented fallback.

### 7. Construct Hourly Carbon

Preferred method:

- Use ENTSO-E hourly generation mix multiplied by standard technology emissions factors.

Fallback:

- Repeat Ember monthly carbon intensity across each month’s hours.

Store the method and source version in `source_artifacts` and `ASSUMPTIONS.md`.

Done when `hourly_energy.carbon_g_kwh` is populated for optimizer zones.

### 8. Build Feature Engineering

- Compute all per-cell features for `SE,DE,IE` first.
- Blend Ember Grids hub/country congestion with OPF line loading and nodal price spread.
- Normalize score inputs with percentile clipping.
- Expand to full Europe only after subset validation passes.

Done when every searchable H3 cell has complete features or explicit missing-data flags.

### 9. Train AlphaEarth Land Suitability

- Sample suitable and unsuitable land points.
- Train Earth Engine Random Forest on AlphaEarth embeddings.
- Export `buildable_fraction` and `dc_similarity` per H3 cell.
- Start on subset countries, then expand.

Done when held-out labels and manual map checks are acceptable.

### 10. Train Siting Model

- Positives: OSM and curated known data-center cells.
- Negatives: non-excluded cells, 3 to 5 negatives per positive.
- Use geography-based splits to avoid leakage.
- Train LightGBM.
- Export score and SHAP explanations.

Done when AUC, precision@k, and feature importance are saved in `eval/`.

### 11. Implement Scoring

- Hard-filter exclusions and insufficient headroom.
- Score additively across price, carbon, congestion, grid distance, connectivity, land, and ML viability.
- Return full score breakdown.

Done when `/sites/search` can explain every top recommendation.

### 12. Implement Optimizer

- Build a single-site LP with grid import, PPA wind/solar, on-site solar, battery, curtailment, and optional backup.
- Enforce hourly energy balance, grid limit, storage state of charge, and optional carbon cap.
- Sweep 8 to 12 carbon caps for the Pareto frontier.
- Output cost, carbon, portfolio, dispatch summary, annual matched clean share, and 24/7 hourly matched CFE share.
- Stretch: flat vs spiky training load toggle.

Done when the optimizer returns a valid Pareto frontier in seconds for one site.

### 13. Build FastAPI Service

- Core first: layers, search, details, compare, optimize.
- Add chat only after deterministic endpoints are stable.
- Add validation, typed responses, cache keys, and clear errors.

Done when pytest covers scoring, endpoint schemas, and optimizer invariants.

### 14. Build Frontend

- First screen is the working map.
- Add MW input, workload selector, scale-band warnings, layer toggles, ranked list, detail drawer, comparison view, Pareto chart, dispatch chart, and assumptions panel.
- Add chat panel after map/search/optimizer work.

Done when the 280 MW demo flow works end to end.

### 15. Build Grounded Agent

- Tools: `search_sites`, `get_site_details`, `compare_sites`, `optimize_supply_mix`, `lookup_context`.
- Build `lookup_context` from chunked IEA Energy and AI report plus `ASSUMPTIONS.md`.
- Mark RAG as first cut under time pressure.
- Agent rules:
  - Every number must come from tools.
  - Ask one clarifying question only if MW or workload type is missing.
  - Warn for `<20 MW` and `>700 MW`.

Done when golden prompts show correct tool calls and numeric faithfulness.

### 16. Evaluate

- Siting: spatial holdout AUC, precision@k, and weight sensitivity.
- Optimizer: energy balance, state-of-charge validity, carbon cap monotonicity, grid-only baseline, and cross-year backtest.
- Agent: 15 to 20 golden prompts for tool selection and numeric grounding.
- Frontend: smoke test map, overlays, drawer, comparison, optimizer chart, and chat.

Done when evaluation outputs are committed or clearly documented.

### 17. Production Hardening After Demo

- Add worker queue for optimization jobs.
- Add Redis/cache if repeated optimizer calls are slow.
- Add structured logs, request IDs, health checks, data version metadata, and source checksums.
- Convert overlays to PMTiles/CDN-ready assets if GeoJSON becomes heavy.

Done only after map, search, comparison, and Pareto demo are working.

### 18. Prepare Final Demo Docs

- Update README with verified run commands.
- Add `ASSUMPTIONS.md`, limitations, architecture diagram, evaluation results, and source/license notes.
- Rehearse the 280 MW demo twice.
- Do not push.

Done when another engineer can run and demo the project from the README.

## Test Plan

- Run task-zero access checks before implementation.
- Run subset pipeline tests for `SE,DE,IE` before full-Europe data.
- Run backend tests for scoring, validation, endpoint schemas, optimizer constraints, and CFE calculations.
- Run ML eval scripts and save metrics.
- Run frontend lint/typecheck/build once scripts exist.
- Use Playwright for the main demo path.
- Run seeded end-to-end scenario: 280 MW training workload, carbon-heavy search, site comparison, optimizer Pareto.

## Assumptions

- Target path is `public/docs/plan.md`.
- Existing source materials are `public/docs/invertix_datacenter_siting_system_design.md` and the challenge PDFs under `public/challenge`.
- LLM provider remains configurable.
- Current model identifiers must be verified at build time.
- User will commit and push.
