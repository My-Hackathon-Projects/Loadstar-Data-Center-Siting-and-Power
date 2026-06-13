# Loadstar — Demo Rehearsal Checklist

The 280 MW AI training campus path. Two clean passes recommended before the
judges' session. Every step is independently runnable from the README; this
file is the time-boxed walkthrough plus rehearsal log appendix.

## Preconditions

- Python 3.13.2 active in the shell (`python3 --version`).
- Docker available (`docker compose version`); the repo ships a
  `docker-compose.yml` that brings up Postgres on `localhost:5432`.
- `.env` at the repo root with `OPENAI_API_KEY` set if you want the live LLM
  pill; the demo works either way.
- Frontend deps installed (`cd frontend && npm install`).

## 10-step rehearsal

1. **Apply schema:**

   ```bash
   docker compose up -d              # Postgres on :5432
   python3 -m backend.db.migrate     # idempotent
   ```

   Confirm the four tables exist (`docker compose exec postgres psql -U loadstar -d loadstar -c '\dt'`).

2. **Run the pipeline (rehydrates fixtures):**

   ```bash
   python3 -m backend.pipeline.subset_ingestion --countries SE,DE,IE
   python3 -m backend.pipeline.hourly_carbon --countries SE,DE,IE
   python3 -m backend.pipeline.alphaearth_land --countries SE,DE,IE
   python3 -m backend.pipeline.feature_engineering --countries SE,DE,IE
   python3 -m backend.pipeline.siting_model --countries SE,DE,IE
   python3 -m backend.pipeline.feature_engineering --countries SE,DE,IE
   ```

   The second `feature_engineering` rehydrates the site features artifact
   with the freshly computed siting-model output.

3. **Generate the static map overlays:**

   ```bash
   python3 -m backend.pipeline.build_layer_assets
   ```

   Confirm `frontend/public/layers/*.json` is populated. The SPA prefers
   these; the live `/layers/{name}` API endpoint stays as fallback.

4. **Start backend + frontend in two shells:**

   ```bash
   # shell A — repo root, API on :8000
   uvicorn main:app --reload

   # shell B — `frontend/`, Vite on :5173
   cd frontend && npm run dev
   ```

5. **Open the SPA and inspect health:**

   ```bash
   open http://127.0.0.1:5173
   curl -fsS http://127.0.0.1:8000/health | jq
   ```

   The `/health` JSON should show `status: "ok"`, `data_mode: "fixture"`,
   `version`, `git_sha`, `uptime_seconds > 0`, and a `dependencies` block
   with the Postgres status as `ok`.

6. **Search 280 MW training, top_k=5.** In the search panel set MW to 280,
   workload to "training", results to 5. Lulea/Boden (SE) should rank first.
   Warnings list should be empty.

7. **Inspect a ranked detail.** Click Lulea/Boden in the ranked list. The
   detail drawer shows headroom, price, carbon, congestion, the SHAP-style
   contribution breakdown, and the LightGBM viability score.

8. **Pin two cells and compare.** Pin Lulea/Boden + Frankfurt West. The
   comparison table should highlight headroom, price, carbon, congestion,
   and viability differences.

9. **Run optimize for Lulea/Boden, 280 MW, flat 24/7.** The Pareto chart
   should populate with eight to twelve points; the dispatch panel should
   show 24 hours; `solver_status` should be `optimal`.

10. **Re-run the same optimize.** The second call should be visibly faster.
    In the API logs (the `uvicorn` shell), find the `optimize.solved` JSON
    record with `cache_hit: true` and the same `cache_key` as the first
    call.

11. **Bonus — async optimizer + chat:**

    ```bash
    JOB=$(curl -fsS -X POST http://127.0.0.1:8000/optimize/supply-mix/async \
        -H 'content-type: application/json' \
        -d '{"cell_id":"8508c683fffffff","load_mw":280,"load_profile":"flat_24_7"}' \
        | jq -r '.job_id')
    sleep 1
    curl -fsS "http://127.0.0.1:8000/optimize/jobs/$JOB" | jq '.status, .solve_ms'
    ```

    Status should be `completed`, `solve_ms` populated. Then trigger the
    chat panel ("Send" button) — the bubble should render with a
    `Live · gpt-4o-mini` or `Deterministic template` pill.

## Smoke checks (one-shot bash)

```bash
curl -fsS http://127.0.0.1:8000/health | jq '.status, .dependencies'
curl -fsS http://127.0.0.1:8000/meta/source-artifacts | jq '.data_version, .artifact_count'
curl -fsS -X POST http://127.0.0.1:8000/sites/search \
    -H 'content-type: application/json' \
    -d '{"power_mw":280,"workload_type":"training","top_k":3}' | jq '.results[0].site.region_name'
curl -fsS -X POST http://127.0.0.1:8000/optimize/supply-mix \
    -H 'content-type: application/json' \
    -d '{"cell_id":"8508c683fffffff","load_mw":280,"load_profile":"flat_24_7"}' | jq '.solver_status, .pareto_frontier | length'
```

Expected outputs:

- `/health` `status` is `"ok"` and `dependencies.postgres.status` is `"ok"`.
- `/meta/source-artifacts` returns a 20-character `data_version` and at
  least seven artifacts after the pipeline rehydration.
- The first ranked region is `Lulea / Boden`.
- `solver_status` is `"optimal"` and the Pareto frontier has at least two
  points.

## Recovery — if the map fails

If the deck.gl + maplibre tiles fail to render in the browser:

1. Click any cell in the ranked list — the detail drawer still works.
2. Use `curl -fsS http://127.0.0.1:8000/sites/search -X POST ...` and read
   the JSON live; the search and Pareto demos do not depend on the map.
3. Confirm the static overlays exist: `ls -la frontend/public/layers/`.
   Re-run `python3 -m backend.pipeline.build_layer_assets` if needed.

## Recovery — if the optimizer is slow

The first call solves up to 11 LPs. If it feels slow:

1. Confirm `scipy` is installed: `python3 -c "import scipy; print(scipy.__version__)"`.
2. Run the second call — the LRU cache turns it into a sub-50ms response.
3. Check `uvicorn` logs for the `optimize.solved` record; `solve_ms`
   should be sub-second on a modern laptop.

## Rehearsal log

Append one block per rehearsal pass.

### Pass 1 — 2026-06-13 (post-implementation smoke)

| Step | Result | Notes |
|---|---|---|
| 1 — migrate | ☑ ok | `python3 -m backend.db.migrate` applied 002 + 003 against the local Postgres. `optimization_runs` schema includes `status`, `started_at`, `completed_at`, `error_message`, `solve_ms`, `request_id`. |
| 2 — pipeline | ☐ ok / ☐ fail | (Skipped this pass; existing artifacts already present.) |
| 3 — layer-assets | ☑ ok | 7 files emitted under `frontend/public/layers/`. |
| 4 — dev | ☑ ok | uvicorn on :8765 for the smoke; SPA `npm --prefix frontend run dev` deferred to live demo. |
| 5 — /health | ☑ ok | `version=0.0.0`, `git_sha=cf132ee`, `uptime_seconds=13.21`, `dependencies.postgres.status=ok`, `dependencies.redis.status=disabled`. |
| 6 — search | ☑ ok | top region: Lulea / Boden; composite_score=0.770 |
| 7 — detail drawer | ☐ verify in UI | Tested via API; SPA path is the rehearsal-2 task. |
| 8 — compare | ☐ verify in UI | API-level only this pass. |
| 9 — optimize (first call) | ☑ ok | solver_status=optimal, pareto frontier=10 points, ~298 ms. |
| 10 — cache hit (second call) | ☑ ok | second call ~10 ms; same cache_key. |
| 11 — async + chat | ☑ ok | async POST 202 → polled status=completed, solve_ms=301.69; idempotent re-post returned same job_id; `/agent/explain` returned `source=template`, model=None (LLM disabled). |

**Pass 1 verdict:** API surface and cache verified. UI walkthrough remains for pass 2 (live demo with the SPA running).

### Pass 2 — YYYY-MM-DD HH:MM

(Run during the live judges' demo. Append the same template once verified end-to-end through the SPA.)
