# Loadstar — Data-Center Siting and Power

[![CI](https://img.shields.io/badge/tests-96%20backend%20%2B%2028%20frontend-brightgreen)](#validation) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![Stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20Vite%20%2B%20React-informational)](#stack)

Loadstar is a decision-support product for the Invertix **Data-Center Siting & Power** challenge. Given a target megawatt size and a workload type, it ranks European data-center sites by composite score, lets a user explore tradeoffs across price, carbon, congestion, grid headroom, connectivity, land suitability, and ML viability, runs a real linear-programming supply-mix optimizer for the selected site, and explains the result in natural language through a real conversational LLM agent (Fred) with a deterministic fallback.

This README is the single judge-facing entry point. Deeper docs are linked from each section.

> **Five-minute demo:** start the API + SPA, click `begin the journey`, speak `find the cheapest 280 MW site in Sweden`, watch Fred fly the map to Lulea/Boden, then ask `what about Germany instead?`. See [Demo flow](#demo-flow).

---

## Table of contents

1. [What it does](#what-it-does)
2. [Demo flow](#demo-flow)
3. [Quick start](#quick-start)
4. [Architecture](#architecture)
5. [Stack](#stack)
6. [ML and data pipeline](#ml-and-data-pipeline)
7. [Scoring engine](#scoring-engine)
8. [Supply-mix optimizer](#supply-mix-optimizer)
9. [Fred (conversational LLM agent + voice)](#fred-conversational-llm-agent--voice)
10. [Fallback design](#fallback-design)
11. [Configuration](#configuration)
12. [Deployment (Vercel)](#deployment-vercel-single-project)
13. [Validation](#validation)
14. [Repository layout](#repository-layout)
15. [API surface](#api-surface)
16. [Limitations and what is still missing](#limitations-and-what-is-still-missing)
17. [Source / license notes](#source--license-notes)

---

## What it does

Three things, in order:

1. **Rank sites.** Given a load (MW), workload type, optional country filter, and per-factor weights, the scoring engine filters out excluded cells and cells with insufficient grid headroom, then ranks the rest by an additive composite score across seven factors (price, carbon, congestion, grid distance, connectivity, land, ML viability). Every result carries a per-factor breakdown and a human-readable explanation.

2. **Explain a site.** For a selected cell, the API returns a full feature payload (price, carbon, headroom, fiber distance, water distance, AlphaEarth-derived buildable land share, LightGBM viability) and runs a single-site supply-mix linear program that returns a Pareto frontier (cost vs carbon), a recommended portfolio, hourly dispatch, annual matched clean share, and 24/7 carbon-free-energy share.

3. **Carry a conversation.** Fred is a real OpenAI tool-calling agent that decides when to invoke `search_sites` (running the live engine) and `explain_site` (calling the explanation service). A regex-driven deterministic fallback keeps the demo working when OpenAI is unconfigured or errors. ElevenLabs text-to-speech runs on the landing screen; the dashboard chat is text-only Markdown so judges can read structured results.

The walking skeleton ships with a curated 81-cell, 30-country European dataset (`backend/engine/data/europe_sites.json`). When the trained ML pipeline runs (`SE,DE,IE` subset), its `lightgbm_score`, `buildable_fraction`, and `dc_similarity` values **overlay** the curated base instead of replacing it — so the map covers the full continent while ML-touched cells reflect real model output.

---

## Demo flow

1. Open `http://127.0.0.1:5173`.
2. Click **begin the journey**. The cinematic intro types the final line `we are building their synthesis` character-by-character, settles, then the globe crossfades in.
3. Fred greets via ElevenLabs voice: `Hello, my name is Fred. How can I help you today?`. The microphone activates.
4. Speak a request: `I want to build a 200 MW AI training campus in EU. Carbon matters more than latency.`
5. Fred says `Sure, here is the result.` and the dashboard appears. The chat panel is pre-seeded with your voice transcript and the LLM's structured Markdown reply (bold site names, numbered list of candidates with carbon / price / headroom on indented bullets).
6. Map flies to the top pick. Click any cell → site detail drawer renders with sparklines.
7. Type a follow-up: `what about Germany instead?`. Fred re-runs the search with the prior 200 MW + carbon priority carried forward and the country filter swapped to DE.
8. Click a cell → the supply-mix optimizer panel populates with Pareto frontier, recommended portfolio, hourly dispatch.
9. Type `what is the composite score?`. Fred answers conversationally without changing the map (no tool call).

Full step-by-step rehearsal: [`public/docs/demo_rehearsal.md`](public/docs/demo_rehearsal.md).

---

## Quick start

Requirements: Python 3.13+, Node 24+, npm. Optional: Docker (for Postgres), an OpenAI key (for live Fred), ElevenLabs key + voice id (for voice on the landing screen).

```bash
# 1. install deps
python3 -m pip install -r requirements.txt
npm --prefix frontend install

# 2. (optional) Postgres for the async optimizer + observability tables
docker compose up -d
python3 -m backend.db.migrate

# 3. (one-time) build the static frontend assets the SPA reads in browser-only mode
node scripts/build_europe_dataset.mjs
python3 -m backend.pipeline.build_layer_assets

# 4. run
uvicorn main:app --reload          # FastAPI on :8000
npm --prefix frontend run dev      # Vite on :5173
```

Open `http://127.0.0.1:5173` and follow the [demo flow](#demo-flow).

If you do not configure Postgres / Redis / OpenAI / ElevenLabs, every dependent feature degrades gracefully — see [Fallback design](#fallback-design).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Vite + React 18 SPA                        │
│  Cinematic intro ─→ Dashboard ─→ Map / Detail / Optimizer / Fred    │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │  REST + X-Request-ID
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                            FastAPI                                  │
│  Middleware: request_id, JSON logs                                  │
│  Routers: meta, sites, optimizer, agent                             │
│  Services: site, optimizer (sync + async), llm, agent, tts          │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                ┌──────────────────┼─────────────────────┐
                ▼                  ▼                     ▼
   ┌─────────────────┐  ┌────────────────────┐  ┌────────────────────┐
   │ engine.scoring  │  │ engine.optimizer   │  │ services.agent     │
   │  + fixtures     │  │  scipy.linprog     │  │  OpenAI Responses  │
   │ (81-cell base)  │  │  highs solver      │  │  + tool calling    │
   └────────┬────────┘  └────────┬───────────┘  └────────┬───────────┘
            │                    │                       │
            ▼                    ▼                       ▼
   ┌─────────────────┐  ┌────────────────────┐  ┌────────────────────┐
   │ pipeline JSON   │  │ optimization_runs  │  │ ElevenLabs TTS     │
   │  (overlay)      │  │  (Postgres)        │  │  (server-side key) │
   │ LightGBM +      │  │  result_cache      │  │                    │
   │ AlphaEarth      │  │  (LRU or Redis)    │  │                    │
   └─────────────────┘  └────────────────────┘  └────────────────────┘
```

**Request flow** (concrete example: `POST /agent/chat`):

```
SPA FredPanel ── POST /agent/chat (history, message, power_mw, workload, selected_cell_id)
              ──> agent_router.chat()
              ──> agent_service.chat()
                    │
                    ├─ if LOADSTAR_LLM_ENABLED + key:
                    │   ├─ _run_llm_agent: OpenAI Responses API with tools=[search_sites, explain_site]
                    │   │   ├─ tool call → search_site_cells() → site_repository.list_sites()
                    │   │   │                                          ├─ pipeline JSON (LightGBM+AlphaEarth)
                    │   │   │                                          └─ overlay onto curated 81-cell base
                    │   │   ├─ tool call → llm_service.explain_site()
                    │   │   └─ final reply: Markdown with verbatim engine numbers
                    │   └─ on any exception → fall through
                    └─ deterministic fallback:
                        regex intent parser → search_site_cells() → optional OpenAI rephrase
              ──> AgentChatResponse { source, model, message, action, cache_key }
              ──> SPA: append to chat, apply action.search → setSearchParams + setSelectedCellId
```

**Frontend → backend resilience.** A one-time `/health` probe (`frontend/src/api/dataSource.ts`) decides at boot whether to hit the live API or fall back to static assets:

- **Live API path:** REST as drawn above.
- **Static-only path** (e.g. Vercel deploy without an API origin): map / search / detail / compare run in-browser via a TypeScript port of the Python scoring engine (`frontend/src/lib/siteEngine.ts`), pinned to backend output by a golden test (`siteEngine.test.ts`). Optimizer shows a "live engine required" placeholder. Fred falls back to the deterministic search.

Full Mermaid diagrams (request flow, pipeline DAG, observability sequence, cache layers, async optimizer): [`public/docs/architecture.md`](public/docs/architecture.md).

---

## Stack

### Backend

| Layer | Choice | Why |
|---|---|---|
| Web framework | **FastAPI** | Async, OpenAPI generation, Pydantic models match wire shape one-to-one. |
| Domain models | **Pydantic v2** | Boundary validation. The scoring engine, optimizer, and pipeline all share `SiteFeature`. |
| Optimizer | **scipy.optimize.linprog** with HiGHS | LP-shaped problem (24-hour single-site dispatch + Pareto sweep), no commercial solver needed. |
| ML | **LightGBM** + **scikit-learn** | Boosted trees fit on H3 cell features; falls back to a transparent composite scorer when LightGBM cannot load. |
| Earth observation | **earthengine-api** + **AlphaEarth** | Random-forest land-suitability classifier on `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`; falls back to a fixture proxy. |
| Network model | **PyPSA** | Topology and clustered OPF artifacts; the demo path uses precomputed OPF. |
| Storage | **PostgreSQL** | `optimization_runs` (job state), `h3_cells`, `site_features`, `hourly_energy`. SQLite (`source_artifacts.db`) is used only for pipeline metadata. |
| Cache | **In-process LRU** (default) or **Redis** (if `REDIS_URL` set) | Identical contract; flip on by env var. |
| LLM | **OpenAI Responses API** with tool-calling | `search_sites` + `explain_site` tools; deterministic regex fallback. |
| Voice | **ElevenLabs TTS** via `httpx` | Server-side key never reaches the browser. Browser Web Speech API does the STT. |
| Observability | stdlib `logging` with JSON formatter, `X-Request-ID` middleware | Every log line includes `request_id`, every endpoint includes a `cache_key`. |
| Tooling | **ruff**, **pyright** (strict), **pytest** | Strict mode on `backend/api`, `backend/engine`, `backend/pipeline`. |

### Frontend

| Layer | Choice | Why |
|---|---|---|
| Build | **Vite** | Fast HMR, modern ESM, code splitting. |
| Framework | **React 18** + **TypeScript** | Strict ESLint + `@typescript-eslint/no-explicit-any`. |
| Maps | **MapLibre GL** + **deck.gl H3HexagonLayer** | Globe projection on the intro, H3 overlays on the dashboard. |
| Charts | **Recharts** | Pareto frontier, hourly dispatch, supply mix. |
| State | **Zustand** | Search-form state shared by the spec bar and the map. |
| Server cache | **TanStack Query** | All API calls go through `frontend/src/lib/queries.ts`; components do not call `fetch`. |
| Animations | **framer-motion** | Cinematic intro, narrative typewriter, card transitions. |
| 3D intro | **three** + **@react-three/fiber** | Starfield warm-up phase only; lazy-loaded so reduced-motion users skip three entirely. |
| Markdown | **react-markdown** | Fred's structured replies render as real bold + lists, not raw asterisks. |
| Voice STT | **Web Speech API** | Browser-native; no third-party STT key. |
| Voice TTS | `/agent/speech` proxy → ElevenLabs | API key stays server-side. |

---

## ML and data pipeline

The pipeline is a Typer-CLI DAG that produces JSON artifacts under `data/processed/subset/` and upserts checksum/source rows into `source_artifacts.db`. Every step is idempotent and accepts `--countries`.

```
subset_ingestion ──┬──> manifest.json
                   ├──> pypsa_network_subset.json
                   ├──> pypsa_clustered_opf.json
                   ├──> hourly_energy_subset.json
                   ├──> ember_grids_congestion_layers.json
                   ├──> osm_site_feature_layers.json
                   └──> connectivity_fiber_or_ixp.json

hourly_carbon ────────> hourly_carbon_subset.json   (ENTSO-E preferred, Ember monthly fallback)

alphaearth_land ──────> alphaearth_land_subset.json (AlphaEarth RF preferred, fixture proxy fallback)

feature_engineering ──> site_features_subset.json   (blends all upstream + 5/95 percentile clip normalize)

siting_model ─────────> siting_model_subset.json    (LightGBM preferred, transparent composite fallback)
                  └───> eval/siting_model_metrics.json (AUC, precision@k, importance)

feature_engineering ──> site_features_subset.json   (rehydration: embeds lightgbm_score + SHAP)
```

**Full pipeline run:**

```bash
python3 -m backend.pipeline.subset_ingestion --countries SE,DE,IE
python3 -m backend.pipeline.hourly_carbon --countries SE,DE,IE
python3 -m backend.pipeline.alphaearth_land --countries SE,DE,IE
python3 -m backend.pipeline.feature_engineering --countries SE,DE,IE
python3 -m backend.pipeline.siting_model --countries SE,DE,IE
python3 -m backend.pipeline.feature_engineering --countries SE,DE,IE   # rehydration
python3 -m backend.pipeline.build_layer_assets                        # static map overlays
```

**Trained-model wiring (where ML reaches scoring):**

| Model | Output field | Consumer |
|---|---|---|
| LightGBM siting classifier (`backend/pipeline/siting_model_trainer.py`) | `lightgbm_score` per cell | `engine.scoring._SCORE_FACTORS["ml"]` (weight 0.08) |
| AlphaEarth Random Forest (`backend/pipeline/alphaearth_land_earth_engine.py`) | `buildable_fraction`, `dc_similarity` per cell | `engine.scoring._SCORE_FACTORS["land"]` blends both (weight 0.08) |

**Where the ML output reaches the API.** The `site_repository` (`backend/api/repositories/site_repository.py`) reads `data/processed/subset/site_features_subset.json` if present, validates each record against `SiteFeature`, and **overlays** matching cells onto the curated 81-cell base. The fixture stays the source of truth for cells the pipeline did not touch, so:

- The map covers all 81 cells (30 countries).
- The 15 `SE,DE,IE` cells the pipeline ran on get **trained** `lightgbm_score`, `buildable_fraction`, `dc_similarity`.
- A schema regression in the pipeline output drops only the offending records, never the whole list (per-record `model_validate`).

---

## Scoring engine

`backend/engine/scoring.py` ranks eligible cells with a deterministic additive composite score over seven factors. Factor names, default weights (sum = 1.0), and inputs:

| Factor | Default weight | Direction | Input field(s) |
|---|---|---|---|
| `price` | 0.18 | lower is better | `mean_price_eur_mwh` |
| `carbon` | 0.24 | lower is better | `carbon_intensity_g_kwh` |
| `congestion` | 0.18 | lower is better | `congestion_index` |
| `grid` | 0.14 | lower is better | `dist_hv_substation_km` |
| `connectivity` | 0.10 | composite | mean of normalized `dist_fiber_km`, `dist_ixp_km`, `latency_proxy_ms` |
| `land` | 0.08 | composite | mean of normalized `buildable_fraction`, `dc_similarity` (both higher-is-better) — **AlphaEarth output** |
| `ml` | 0.08 | higher is better | `lightgbm_score` — **LightGBM trained model output** |

Normalization is **5/95 percentile clipping**, not min-max — so a single outlier cell cannot dominate the rescale. Hard filters: `exclusion_flag=True` and `headroom_mw < requested power` are dropped before ranking.

Every factor surfaces a `raw_value` string in `score_explanations` (e.g. `72% buildable / 81% data-center similarity` for `land`) so the UI's detail drawer and Fred's explanations can name the source field. Tests pin every factor's wiring (`backend/tests/engine/test_scoring.py`).

---

## Supply-mix optimizer

`backend/engine/optimizer_model.py` builds a 24-hour single-site linear program with seven dispatch sources (grid import, wind PPA, solar PPA, on-site solar, battery charge/discharge, curtailment, optional backup), an hourly energy balance, grid headroom, storage state of charge, and an optional carbon cap.

- ~270 decision variables, ~217 constraints, solved with `scipy.optimize.linprog(method="highs")`.
- Up to 11 solves per request: 1 recommended portfolio + up to 10 Pareto frontier points across 9 carbon-cap scenarios.
- Sync endpoint `POST /optimize/supply-mix` returns immediately (LRU-cached on identical requests).
- Async endpoint `POST /optimize/supply-mix/async` returns 202 with a `job_id`; status polled at `GET /optimize/jobs/{job_id}` via the `optimization_runs` table.

**Idempotency:** before inserting a `pending` row, the service looks up any `completed` row with the same `cache_key` and returns its `job_id`. Two identical async POSTs produce one solve.

Response includes `recommended_portfolio`, `dispatch_summary`, 24 hourly `dispatch_preview` rows, `annual_matched_clean_share`, `hourly_24_7_cfe_share`, and `pareto_frontier`.

---

## Fred (conversational LLM agent + voice)

Fred is two distinct surfaces with one conversational backend.

**Landing screen (voice):** ElevenLabs TTS plays the greeting, browser Web Speech API does STT. The user's first request is sent to `/agent/chat` while Fred speaks a short acknowledgement (`Sure, here is the result.`); the response is persisted via session storage and the dashboard mounts seeded with both turns of the conversation.

**Dashboard chat (text-only):** A proper multi-turn chat input (auto-grow textarea + Send button) renders Markdown replies. Each assistant bubble shows a source pill: `live · gpt-4o-mini` (LLM drove the turn) or `engine` (deterministic regex fallback). Search actions update the map and filters automatically when the LLM calls the `search_sites` tool; pure conversation turns leave the map untouched.

**Backend:** `backend/api/services/agent_service.py`. Two paths share the same `chat()` entry point and the same `AgentChatResponse` contract:

1. **LLM tool-calling agent (preferred).** When `LOADSTAR_LLM_ENABLED=true` and `OPENAI_API_KEY` is set, the OpenAI Responses API drives the conversation with two function tools — `search_sites` (runs the live engine) and `explain_site` (calls `llm_service.explain_site`). The model never sees free-form numbers it could echo: every figure must come from a tool result, enforced by the system prompt's "Numeric faithfulness" rule. The loop is bounded by 2 tool iterations + an 8s per-call timeout; after the cap a final reply is forced by re-calling without `tools`.

2. **Deterministic regex fallback.** When the LLM is disabled, missing, or errors, a keyword-driven parser builds a `SearchRequest` (parsing country names, MW targets, emphasis terms) and runs the engine. An optional rephrase step calls OpenAI to narrate the deterministic facts when the LLM is configured but the tool-calling path errored.

**Multi-turn refinement:** the system prompt explicitly instructs Fred to treat short follow-ups (`Germany`, `try 100 MW`, `cheaper instead`) as refinements of the most recent search — reuse prior `power_mw`, `workload_type`, `emphasis` unless the user changes them. Validated end-to-end with three-turn integration probes.

---

## Fallback design

Every external dependency has a documented fallback. The demo never breaks because of an offline service.

| Dependency | When unavailable | Fallback | Where logged |
|---|---|---|---|
| OpenAI (Fred LLM) | `LOADSTAR_LLM_ENABLED=false` or key missing or API error | Deterministic regex intent parser → engine search → optional rephrase | `agent.fallback` |
| ElevenLabs (Fred voice) | Key missing | `/agent/speech` returns 503; UI hides the audio path | `tts.upstream_request_error` |
| ElevenLabs (paid voice) | Free-tier account using a library voice | Returns 502 with body preview in log | `tts.upstream_http_error` |
| LightGBM (libomp missing on Mac) | `dlopen` of `lib_lightgbm.dylib` fails | Transparent composite scorer (still per-cell, not constant) | `siting_model_subset.json::source_status: "fallback"` |
| Earth Engine + AlphaEarth | `EARTHENGINE_PROJECT` unset or auth missing | Fixture-shaped land proxy | `alphaearth_land_subset.json::source_status: "fallback"` |
| Postgres | Service down | Async optimizer rejects with 503; sync still works | startup log |
| Redis | `REDIS_URL` unset | In-process LRU cache (256 entries) | `LruResultCache` initialized |
| Pipeline JSON | Missing or malformed | Fixture base only (81 cells, no ML overlay) | `repository.fixture_active` |
| Ember hourly | `EMBER_HOURLY_PRICE_URL` unset | Ember monthly broadcast | `hourly_carbon_subset.json` |

Surface every active fallback at `GET /meta/source-artifacts` (returns checksums + status per artifact + a 20-character data-version fingerprint).

---

## Configuration

All runtime config is read from the single root `.env` (template `.env.example`). The same `Settings` class powers FastAPI and the Typer CLIs.

| Env var | Default | What it does |
|---|---|---|
| `DATABASE_URL` | `postgresql://loadstar:loadstar@localhost:5432/loadstar` | Postgres DSN. `POSTGRES_URL` is a Vercel/Supabase fallback when this is unset. |
| `REDIS_URL` | (unset) | Set to `redis://...` to swap the optimizer cache from in-process LRU to Redis. |
| `LOADSTAR_LLM_ENABLED` | `false` | **Set to `true` to activate Fred's LLM tool-calling agent.** |
| `OPENAI_API_KEY` | (unset) | Required when `LOADSTAR_LLM_ENABLED=true`. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Override to use a different model. |
| `ELEVENLABS_API_KEY` | (unset) | Required for voice TTS. |
| `ELEVENLABS_VOICE_ID` | (unset) | Required for voice TTS. **Use a stock voice (e.g. `pNInz6obpgDQGcFmaJgB` Adam, `ErXwobaYiN019PkySvjV` Antoni) on Free; library voices return 402.** Typo-alias `ELEVEBLABS_VOICE_ID` is also accepted. |
| `ELEVENLABS_MODEL` | `eleven_multilingual_v2` | TTS model. |
| `ELEVENLABS_OUTPUT_FORMAT` | `mp3_44100_128` | Audio format. |
| `ELEVENLABS_TIMEOUT_SECONDS` | `15.0` | Upstream request timeout. |
| `LOG_FORMAT` | `json` | `text` for human-readable demo logs. |
| `LOGGING_LEVEL` | `INFO` | stdlib log level. |
| `EMBER_API_KEY` | (unset) | Optional Ember API token. |
| `EMBER_HOURLY_PRICE_URL` | (unset) | Verified Ember hourly endpoint. Without it, hourly-carbon falls back to the monthly broadcast. |

`EARTHENGINE_PROJECT` (used by the AlphaEarth CLI) is currently a CLI-only flag, not bound to `Settings`. See [Limitations](#limitations-and-what-is-still-missing).

---

## Deployment (Vercel, single project)

The whole product runs from one Vercel project: the FastAPI app is deployed as a single Python Serverless Function (`tool.vercel.entrypoint = backend.api.main:app` in `pyproject.toml`) and that app also serves the built SPA and its static assets. There is no separate frontend host and no CORS to manage; everything is same-origin.

- `vercel.json` builds the SPA (`npm --prefix frontend run build`) so `frontend/dist` is bundled into the function, then trims tests/data/ml from the bundle with `functions.excludeFiles`.
- `backend/api/main.py` mounts `/assets`, `/fonts`, `/geo`, `/data`, and the prebuilt `/layers/{name}.json`, serves `index.html` for the SPA routes (`/`, `/tech`, `/thanks`), and keeps real API 404s.
- The frontend runs a one-time `/health` probe (`frontend/src/api/dataSource.ts`). On Vercel the function answers `/health`, so search, the supply-mix optimizer, and Fred (LLM + deterministic parser) all use the **live API**. If the API is ever unreachable, the SPA degrades to an in-browser scoring engine (`frontend/src/lib/siteEngine.ts`, pinned to the Python output by `siteEngine.test.ts`) so search/detail/compare keep working.

Deploy steps:

```bash
vercel --prod        # or push to the connected Git branch
```

Vercel environment variables (Project Settings → Environment Variables):

- `OPENAI_API_KEY` and `LOADSTAR_LLM_ENABLED=true` — enables Fred's live LLM (without them Fred uses the deterministic parser, still server-side).
- `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` — enables Fred's voice on the landing screen (use a stock voice ID on Free tier).
- `DATABASE_URL` / `POSTGRES_URL` — Postgres for `/health` status, the async optimizer, and `/meta/source-artifacts`. The core path (search, sync optimizer, Fred) works without it.
- Do **not** set `WEB_DIST_DIR` (it defaults to `frontend/dist`, which is what the build produces).

If the project was previously deployed as a static site, set the Vercel Framework Preset to detect the Python app (the `fastapi` dependency plus `pyproject.toml`'s `[tool.vercel]` entrypoint), then redeploy.

---

## Validation

```bash
python3 -m ruff check backend                      # lint
python3 -m pyright backend/api backend/engine backend/pipeline   # strict typecheck
python3 -m pytest                                  # 96 backend tests + 9 skipped (env-gated)
npm --prefix frontend run lint                     # ESLint strict + React-hooks rules
npm --prefix frontend run typecheck                # tsc -b
npm --prefix frontend run test -- --run            # 28 vitest tests
npm --prefix frontend run build                    # production build
```

**Test coverage highlights:**

- Search validation, scale-band warnings, deterministic additive scoring, score explanations.
- ML/land factor wiring pinned: `ml` consumes `lightgbm_score`, `land` blends `buildable_fraction` + `dc_similarity`, `ml`/`land` weights = 0.08, weight changes propagate to contributions.
- Pipeline output schema validated against `SiteFeature` end-to-end.
- Repository merge semantics: pipeline overlays onto fixture base, malformed records dropped record-by-record, fixture intact when artifact missing/corrupt.
- Optimizer energy balance, storage bounds, carbon caps, spiky-load shape.
- Async optimizer 202 + status polling, idempotent enqueue.
- LRU cache hit/miss/eviction.
- Agent: LLM path used when enabled, search action invoked, fallback when LLM returns None, history forwarding, deterministic-path coverage when LLM disabled.
- TTS configuration error → 503; live path patched per-test.
- LLM explain endpoint: template / fallback / live response paths.
- Frontend siteEngine parity test re-derives the backend `composite_score.json` cell-for-cell (rounding tolerance 1e-3).
- Static SPA path (`dataSource.ts`) decides live vs static at boot via `/health` probe.
- Cinematic-intro reducer transitions, formatters, score explanation strings, optimizer chart transforms.

**Generate the OpenAPI types** after API surface changes (requires the API running on `127.0.0.1:8000`):

```bash
npm --prefix frontend run generate:types
```

---

## Repository layout

```
.
├── backend/
│   ├── api/                # FastAPI routers, services, middleware, core settings
│   │   ├── routers/        # meta, sites, optimizer, agent
│   │   ├── services/       # site, optimizer (sync + async + cache + jobs), llm, agent, tts, meta
│   │   ├── repositories/   # site_repository (fixture base + pipeline overlay)
│   │   ├── middleware/     # request_id
│   │   └── core/           # config (pydantic-settings), logging (JSON formatter)
│   ├── engine/             # pure-python: scoring, optimizer_model, normalization, contracts, fixtures
│   │   └── data/europe_sites.json   # canonical 81-cell, 30-country dataset
│   ├── pipeline/           # Typer-CLI ingestion + ML pipeline (subset, hourly_carbon, alphaearth_land, feature_engineering, siting_model, build_layer_assets, access_check)
│   ├── db/                 # Postgres migrations (000-numbered, idempotent)
│   └── tests/              # mirrors api/, engine/, pipeline/, db/
├── frontend/
│   ├── src/
│   │   ├── features/       # journey, dashboard, search, site-detail, map, optimizer, compare, chat, tech, thanks
│   │   ├── api/            # thin fetch wrappers (sites, agent, optimizer, layers, assumptions)
│   │   ├── lib/            # queries (TanStack), siteEngine (TS port of Python scoring), formatters, fredVoice, fredHandoff, fredPrompt, scoreExplanations
│   │   ├── hooks/          # useSpeechInput, useUiStore (Zustand), useSearchRequest
│   │   ├── components/     # shared UI atoms (Metric)
│   │   ├── config/         # env, defaults
│   │   ├── styles/         # design tokens
│   │   └── types/          # api.ts (re-exports openapi.ts), openapi.ts (generated)
│   └── public/
│       ├── data/           # sites.json + assumptions.json (regenerated)
│       └── layers/         # composite_score.json + 6 raw-field GeoJSON layers (regenerated)
├── scripts/build_europe_dataset.mjs   # canonical Europe-wide dataset generator
├── data/processed/subset/  # pipeline output JSON (gitignored)
├── eval/                   # ML eval metrics
├── public/docs/            # plan, architecture, demo_rehearsal, access_decisions, system_design
├── docker-compose.yml      # Postgres-only stack
├── main.py                 # one-line uvicorn re-export of backend.api.main:app
├── ASSUMPTIONS.md          # numeric assumptions + source notes
├── AGENTS.md               # internal automation routing
└── README.md               # this file
```

---

## API surface

```
GET  /health                       App version, git sha, started_at, uptime, dependency status
GET  /meta/source-artifacts        Pipeline artifact checksums + 20-char data_version fingerprint
GET  /assumptions                  Numeric assumptions (scoring weights, optimizer inputs, scale bands)

GET  /layers/{name}                GeoJSON for one of: composite_score, mean_price_eur_mwh,
                                   carbon_intensity_g_kwh, congestion_index, headroom_mw,
                                   dist_fiber_km, buildable_fraction
POST /sites/search                 Rank cells (power_mw, workload_type, top_k, weights, country_filter)
GET  /sites/{cell_id}              Full SiteFeature payload
POST /sites/compare                Compare 2-5 cells

POST /optimize/supply-mix          Sync solve, LRU-cached
POST /optimize/supply-mix/async    202 + job_id, BackgroundTasks worker
GET  /optimize/jobs/{job_id}       Poll job status

POST /agent/chat                   Conversational tool-calling LLM agent (fallback: deterministic)
POST /agent/explain                Single-cell explanation (fallback: deterministic template)
POST /agent/speech                 ElevenLabs TTS proxy (key stays server-side)
```

Every successful response carries a `cache_key` field. Unknown layers / unknown cells / mis-shaped requests return structured errors:

```json
{ "detail": { "code": "site_not_found", "message": "Unknown site cell: xyz" } }
```

Frontend types are generated from the FastAPI OpenAPI schema into `frontend/src/types/openapi.ts`; `frontend/src/types/api.ts` re-exports the aliases UI code consumes.

---

## Limitations and what is still missing

Honest audit of what is and is not in the box.

**Live and working:**

- Conversational Fred (LLM tool-calling) on dashboard with multi-turn refinement.
- Voice landing screen with ElevenLabs TTS + browser STT.
- Markdown chat rendering with bold + numbered/bulleted lists.
- 81-cell, 30-country curated European dataset feeding map and search.
- ML overlay: trained LightGBM `lightgbm_score` and AlphaEarth land features reach the scoring engine for `SE,DE,IE` cells (when the pipeline has run).
- Sync + async supply-mix optimizer with idempotent enqueue and LRU caching.
- Static-SPA fallback path (Vercel deploy without backend).
- Per-record validation in the repository so a schema regression drops only the bad record.

**Active fallbacks on this machine** (would activate the live path with the right env / install):

| Component | Current state | What turns it real |
|---|---|---|
| LightGBM training | Transparent-composite fallback because `libomp.dylib` is missing | `brew install libomp` (Mac) or system OpenMP runtime |
| AlphaEarth land model | Fixture proxy because no Earth Engine credentials are configured | Run `earthengine authenticate`, set `EARTHENGINE_PROJECT` |
| `EARTHENGINE_PROJECT` plumbing | CLI flag only, not bound to `Settings` / `.env` | Tracked in [What's missing](#whats-missing) |
| ENTSO-E hourly carbon | Ember monthly broadcast fallback | Provide a verified ENTSO-E generation-mix JSON pull |
| Ember hourly prices | Fixture broadcast | Set `EMBER_HOURLY_PRICE_URL` + `EMBER_API_KEY` |
| BBmaps fiber connectivity | IXP-distance proxy | Real BBmaps WMS endpoint |
| OSM substations / water / exclusions | Per-cell fixture proxies | Live OSM extracts |
| PyPSA full OPF | Precomputed stub | Real PyPSA-Eur dataset (Zenodo 18619025) |

**What's missing (would not block submission, but a judge will ask):**

1. **`EARTHENGINE_PROJECT` env-var plumbing.** Today the AlphaEarth CLI accepts `--earthengine-project` but does not read the env var or `Settings`. A user setting `EARTHENGINE_PROJECT=foo` in `.env` sees no effect. The fix is small: add the field to `Settings` + read it in the CLI default. ([Issue traced earlier](#fallback-design).)
2. **Production OpenAI Realtime / streaming voice.** Today Fred's voice on the landing screen uses TTS-on-completion (~1-2 s after agent reply). A judge expecting OpenAI Realtime-style streaming voice will notice the latency.
3. **No live ENTSO-E / Ember pull in the demo.** The pipeline reads the fallbacks; the access-check tool documents what would be required.
4. **Async optimizer is single-process.** `BackgroundTasks` runs in the same uvicorn worker. Multi-node migration is one local change (swap to `arq` / `RQ` / Celery reading the same `optimization_runs` table); the HTTP surface stays unchanged.
5. **PMTiles / vector tiles.** Today's overlays are <50 KB GeoJSON. When any overlay grows past ~5 MB or ~1000 features, regenerate via `tippecanoe` and switch the deck.gl layer to `MVTLayer` or `pmtiles-protocol`.
6. **No PostGIS geospatial joins.** Cells are H3-indexed; spatial queries are dictionary lookups. PostGIS would unlock topology queries (within X km of a substation) but is not on the demo path.
7. **No full-year unit-commitment optimizer.** The current solver is a 24-hour representative LP. A judge asking about seasonality will hear the limitation.
8. **No history persistence.** Fred's chat resets on browser refresh; sessionStorage is cleared. Acceptable for the demo.
9. **No WebSocket streaming for chat.** Replies are blocking POSTs (~3-5 s typical, 8s timeout). A judge used to ChatGPT-style streaming will notice.
10. **Voice on dashboard.** The dashboard is text-only by deliberate UX choice (per user feedback). Voice could be a toggle, but it isn't today.

**Pyright info-level hints** in tests (not errors): a few `**__: Any` placeholder warnings and one `Type of "_factory" is unknown` on the result-cache singleton. These are pre-existing and IDE-only — `pyproject.toml` excludes tests from strict pyright on purpose.

**Documented evaluation results** under `eval/`:

- [`eval/siting_model_metrics.json`](eval/siting_model_metrics.json): LightGBM (or fallback) viability model — `auc = 0.80`, `precision@1 = 1.0`, `precision@3 = 0.67`, `precision@5 = 0.80`, hold-out country = `IE`. Currently `fallback: true` because of the libomp issue above.
- [`eval/alphaearth_land_metrics.json`](eval/alphaearth_land_metrics.json): AlphaEarth metrics — currently `source_status: "fallback"` because Earth Engine credentials are not configured.

Both are deterministic given `DETERMINISTIC_SEED = 20260612`.

---

## Source / license notes

Loadstar source: **MIT** ([`LICENSE`](LICENSE)). The data sources the pipelines read from carry their own terms:

| Source | Use | License | Fallback today |
|---|---|---|---|
| ENTSO-E | Hourly generation mix | Public re-use, attribution required | Ember monthly broadcast |
| Ember | Monthly carbon, hourly prices | CC BY 4.0 | Fixture broadcast |
| PyPSA-Eur (Zenodo 18619025) | Network topology, OPF | CC BY 4.0 | Fixture network + precomputed OPF |
| OpenStreetMap | Substations, water, exclusions, IXP | ODbL 1.0 | Per-cell fixture proxies |
| ITU BBmaps | Fiber connectivity | ITU-D, fair use | IXP distance proxy |
| Google Earth Engine + AlphaEarth | Land suitability | Earth Engine ToS | Transparent composite |
| OpenAI Responses API | Conversational agent | OpenAI ToS | Deterministic template |
| ElevenLabs | Text-to-speech | ElevenLabs ToS | UI hides voice when not configured |

The access-check tool (`python3 -m backend.pipeline.access_check --write public/docs/access_decisions.md`) probes each external source without printing secrets and writes the live status to [`public/docs/access_decisions.md`](public/docs/access_decisions.md).

---

## Further reading

- [`public/docs/plan.md`](public/docs/plan.md) — canonical build plan (issues 1-14).
- [`public/docs/architecture.md`](public/docs/architecture.md) — full Mermaid diagrams.
- [`public/docs/demo_rehearsal.md`](public/docs/demo_rehearsal.md) — 10-step judge rehearsal.
- [`public/docs/invertix_datacenter_siting_system_design.md`](public/docs/invertix_datacenter_siting_system_design.md) — design-doc framing.
- [`public/docs/access_decisions.md`](public/docs/access_decisions.md) — task-zero external-source decisions.
- [`ASSUMPTIONS.md`](ASSUMPTIONS.md) — numeric assumptions and source notes.

---

*Built for the Invertix Data-Center Siting & Power challenge. Deterministic, demo-safe, and honest about its fallbacks.*
