# Loadstar: Data Center Siting and Power

Loadstar is a decision-support product for the Invertix **Data-Center Siting & Power** challenge. It recommends European data-center locations for a requested MW size, explains trade-offs across energy and connectivity constraints, and returns a chart-ready supply-mix optimization response for the selected site.

The current implementation covers issues `#1` through `#5`:

- `public/docs/plan.md` is the canonical build plan.
- `public/docs/access_decisions.md` records task-zero external source checks and downstream fallback implications.
- A fixture-backed walking skeleton exposes the API contracts and a Vite + React + TypeScript demo UI.
- `ASSUMPTIONS.md` centralizes numeric assumptions and source notes.
- `db/001_initial.sql` defines the minimal four-table schema for the first demo slice.

## Repository Layout

- Frontend: `frontend/` contains the Vite + React 18 + TypeScript SPA.
- Backend API: `api/app/` contains FastAPI routers, services, and core settings.
- Backend domain logic: `engine/` contains pure Python scoring and optimizer code.
- Backend data tooling: `backend/pipeline/` contains ingestion and access-check CLIs, and `db/` contains numbered SQL migrations.
- Tests: `tests/` and `backend/tests/` mirror the Python package layout.

## Current Demo Path

The fixture skeleton supports the required first integration path:

1. Enter a 280 MW AI training campus.
2. Search fixture sites in Sweden, Germany, and Ireland.
3. Open a site detail view.
4. Run the fake-but-contract-shaped Pareto optimizer response.

The fixture data deliberately uses the same field names as the planned `site_features` contract so later ingestion issues can swap real data behind the same interface.

## Requirements

- Python 3.12+
- Node 24+ and npm
- Optional: `uv` for Python dependency management

Runtime configuration is read from the single root `.env` file. `.env.example` is the tracked template; `.env` is ignored so local credentials are not committed.

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
npm --prefix frontend install
```

## Run The API And Demo UI

Start the API:

```bash
python3 -m uvicorn api.app.main:app --reload
```

Start the web app in another shell:

```bash
npm --prefix frontend run dev
```

Then open the Vite URL printed by npm, normally:

```text
http://127.0.0.1:5173
```

Useful endpoints:

```text
GET  /health
GET  /layers/composite_score
POST /sites/search
GET  /sites/{cell_id}
POST /sites/compare
POST /optimize/supply-mix
GET  /assumptions
```

Example search:

```bash
curl -sS http://127.0.0.1:8000/sites/search \
  -H "Content-Type: application/json" \
  -d '{"power_mw": 280, "workload_type": "training", "top_k": 5}'
```

## Task-Zero Access Checks

Run the external source check script before replacing fixtures with real data:

```bash
python3 -m backend.pipeline.access_check --write public/docs/access_decisions.md
```

Optional environment variables:

```text
EARTHENGINE_PROJECT       Google Earth Engine project used for an AlphaEarth sample.
EMBER_HOURLY_PRICE_URL    Verified Ember hourly price endpoint for one real pull.
EMBER_API_KEY             Optional Ember API token, if required by the endpoint.
ITU_BBMAPS_TEST_URL       Optional BBmaps feature/WMS test URL.
```

The checker does not print secrets. If a source is blocked, it records the fallback implication so later issues do not rediscover the same decision.

## Apply The Minimal Schema

For the first skeleton batch, the schema is SQLite-compatible so migrations can be tested locally without a database service:

```bash
python3 -m db.migrate --database data/loadstar.db
```

This intentionally creates only:

- `h3_cells`
- `site_features`
- `hourly_energy`
- `optimization_runs`

Later ingestion issues should add their own tables when they populate them.

## Run The Subset Ingestion Pipeline

Issue 6 adds a backend-scoped subset-first artifact command. It accepts a country subset, writes processed JSON artifacts under `data/processed/subset/`, and records source fallback status plus checksums in `source_artifacts`.

```bash
python3 -m backend.pipeline.subset_ingestion \
  --countries SE,DE,IE \
  --output-dir data/processed/subset \
  --metadata-database data/processed/source_artifacts.db
```

The command writes:

- `manifest.json`
- `pypsa_network_subset.json`
- `pypsa_clustered_opf.json`
- `hourly_energy_subset.json`
- `ember_grids_congestion_layers.json`
- `osm_site_feature_layers.json`
- `connectivity_fiber_or_ixp.json`

The command also upserts one `source_artifacts` row per generated artifact, including the manifest. The OPF artifact is always precomputed; no PyPSA solve runs live in the demo path.

## Build Hourly Carbon And Site Features

Issue 7 builds optimizer-ready hourly carbon rows. The preferred method accepts an ENTSO-E generation-mix JSON input and multiplies hourly technology generation by documented emissions factors. Without that input, the active local method repeats Ember-style monthly carbon intensity across each hour in the month.

```bash
python3 -m backend.pipeline.hourly_carbon \
  --countries SE,DE,IE \
  --output-dir data/processed/subset \
  --metadata-database data/processed/source_artifacts.db
```

Issue 8 builds per-cell ranking features from the subset artifacts and hourly carbon output:

```bash
python3 -m backend.pipeline.feature_engineering \
  --countries SE,DE,IE \
  --input-dir data/processed/subset \
  --output-dir data/processed/subset \
  --metadata-database data/processed/source_artifacts.db
```

The feature artifact writes `site_features_subset.json` with complete searchable-cell fields, normalized score inputs, map overlay values, congestion blend components, and explicit missing-data flags for fallback sources.

## Validation

```bash
make lint
make typecheck
make test
```

For a Python-only check while the web dependencies are not installed yet:

```bash
python3 -m pytest
python3 -m pyright api engine backend/pipeline
```

The current tests cover:

- search validation and scale-band warnings
- fixture response shape
- detail and optimizer contracts
- access decision fallback behavior
- applying the four-table schema from zero
- subset ingestion artifacts and source metadata
- hourly carbon preferred/fallback methods
- feature engineering normalization and missing-data flags

## Non-Goals In This Batch

- No full-Europe ingestion yet.
- No PostGIS service requirement yet.
- No real AlphaEarth/LightGBM model training yet.
- No real LP solver yet; the optimizer response is a plausible fixture contract.
- No Git commits or pushes from the agent.
