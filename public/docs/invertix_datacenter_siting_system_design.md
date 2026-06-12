# Loadstar: Data Center Siting and Power

## Complete System Design and Build Document (Invertix Challenge)

---

## 0. Executive Summary

**Loadstar** is a decision support system for siting and powering AI data centers in Europe. Given a facility size in MW, it ranks candidate locations across price, carbon, grid headroom, and connectivity; optimizes the power supply mix (grid, PPA, on-site generation, storage) for any chosen site as a linear program with a cost vs carbon Pareto frontier; and exposes everything through a map with toggleable overlays and a conversational agent whose every number is grounded in the quantitative engine. Data foundations: PyPSA-Eur (grid topology and congestion), Ember (hourly prices and carbon intensity), OpenStreetMap (substations, exchanges, water, exclusions), AlphaEarth satellite embeddings (land suitability and a learned siting model), and the IEA Energy and AI report (assumptions and agent grounding). Heavy computation is precomputed offline; serving is light, cached, and stateless, which is the core of the scaling story.

The name: a lodestar is the star you navigate by, and a data center is, to the grid, a load. Loadstar is the star you navigate large loads by.

---

## 1. Understanding the Problem

### 1.1 What the challenge actually says

The prompt has three explicit deliverables hidden in the "Worth Exploring" section. Treat them as the grading rubric:

1. **Site recommendation.** Given a data center size (in MW), recommend locations and explain the trade-offs.
2. **Supply mix planning.** For a chosen site, plan a mix of grid power, Power Purchase Agreements (PPAs), and on-site generation, optimized against cost and carbon.
3. **Spatial overlay.** Combine capacity, prices, carbon, and congestion into map layers that visually separate good sites from bad sites.

The phrase "help someone reason about where to build" is important. They do not want a black box that prints one coordinate. They want a decision support tool: rankings, explanations, trade-off curves, and an interface a non-expert can interrogate. This is why a conversational agent layer on top of a quantitative engine is the right shape.

### 1.2 Domain context you must be able to speak to in the interview

- AI is driving unprecedented load growth. The IEA projects global data center electricity consumption roughly doubling to about 945 TWh by 2030, just under 3% of global electricity. Data center demand grew 17% in 2025 while total electricity demand grew only 3%.
- The binding constraint has flipped. Historically latency and fiber decided siting. Now power availability is the gating factor. Land, fiber, and water still matter but are secondary to securing firm, scalable, ideally clean power.
- Concentration creates congestion. About half of US data centers under development sit in pre-existing clusters (Northern Virginia is the canonical example; Dublin and Frankfurt are the European equivalents). Clustering raises local grid bottleneck risk, drives up connection queue times, and pushes prices in those zones.
- Supply mix reality. Grid power dominates today. Renewables are the fastest growing source for data centers (roughly 22% annual growth 2024 to 2030, covering about half of demand growth), much of it via PPAs. Gas and on-site generation fill firm capacity gaps, and on-site batteries are becoming critical because AI training loads have fast, large power swings.
- The four-way trade-off in the prompt:
  - **Price**: wholesale electricity price varies enormously across Europe (Nordics and Iberia cheap, Germany and Ireland expensive).
  - **Carbon**: grid carbon intensity varies by an order of magnitude (France and Norway under 50 gCO2/kWh, Poland above 600).
  - **Congestion**: cheap clean zones often have weak grids or long interconnection queues.
  - **Connectivity**: fiber backbones and internet exchanges cluster in exactly the congested metros (Frankfurt, Amsterdam, London, Paris, Dublin, the FLAP-D markets).
- A useful one-liner for your pitch: "The cheapest, cleanest electrons are usually where the fiber is not. Our system quantifies that tension and lets you choose your point on it."

### 1.3 Scope decision: focus on Europe

All five suggested data sources are strongest for Europe (PyPSA-Eur is Europe only, Ember has hourly European prices, ENTSO-E underlies both). Build for Europe, and design the architecture so a new region is just a new data adapter. Say this explicitly when discussing scalability.

---

## 2. The Five Suggested Tools: What Each One Is and What You Use It For

### 2.1 PyPSA-Eur

An open optimization model of the European energy system at transmission network level, covering the full ENTSO-E area. It contains roughly 6000 transmission lines (AC at 220 kV and above, plus all HVDC), about 3650 substations, an open power plant database, hourly demand time series, hourly wind and solar availability time series derived from reanalysis weather data, and land-use-constrained geographic potentials for wind and solar expansion. It is built with a Snakemake workflow and solved with the PyPSA framework (linear optimal power flow and capacity expansion).

**What you use it for:**
- Grid topology: substation locations and line capacities define where a large load can physically connect.
- Congestion signal: run (or use precomputed results of) a linearized optimal power flow. Line loading percentages and nodal price differences are your congestion metric.
- Renewable resource quality: capacity factor time series per region tell you how good an on-site or nearby PPA solar/wind project would be.
- The supply mix optimizer itself: PyPSA the framework (not the full Eur model) is the cleanest way to formulate the single-site dispatch and investment LP.

**Critical hackathon warning:** building PyPSA-Eur from raw data takes hours and tens of GB. Do not do it live. Use the prebuilt network files published on Zenodo (there is a prebuilt OSM-based electricity network for PyPSA-Eur), or pre-solve a clustered network (for example 50 to 100 nodes) before the event and ship the solved NetCDF file with your repo.

### 2.2 Ember data

An energy think tank publishing fully open (CC-BY-4.0) electricity data with a free API (api.ember-climate.org). Coverage: yearly generation, capacity, emissions, demand, and carbon intensity for over 200 geographies; monthly data for about 88; and, most valuable for you, hourly European wholesale day-ahead electricity prices per country, sourced from ENTSO-E and cleaned.

**What you use it for:**
- Price layer: average and hourly day-ahead prices per bidding zone. This is the "price" axis of the trade-off.
- Carbon layer: carbon intensity (gCO2/kWh) per country, yearly and monthly. This is the "carbon" axis.
- Hourly price and a derived hourly carbon intensity series are the inputs to the supply mix LP (you optimize against 8760 hourly values, not one annual average).

### 2.3 OpenStreetMap

Queried through the Overpass API or regional extracts from Geofabrik.

**What you use it for:**
- Substations and lines: `power=substation`, `power=line` with voltage tags. Distance to the nearest high voltage substation is a first-order proxy for connection cost and time.
- Connectivity: `telecom=*` features, internet exchange points, and major cities as fiber proxies. Honest framing: OSM fiber data is sparse, so use distance to internet exchange points and metro areas as the connectivity proxy and say so.
- Water: rivers and lakes for cooling water access.
- Exclusions: protected areas, airports, dense residential land use, floodplains.
- Existing data centers: `building=data_center` and `telecom=data_center` tags give you positive training labels for the ML model.

### 2.4 IEA Energy and AI report

Not a dataset but the analytical backbone. Use it for: demand growth scenarios, typical data center load characteristics (servers about 60% of load, cooling 7% to 30% depending on climate and design), the supply mix outlook, the clustering and bottleneck findings, and PUE assumptions. Cite it in your assumptions panel. Also use it as the RAG corpus for your agent so the agent answers contextual questions ("why is congestion a problem?") with grounded text instead of hallucinating.

### 2.5 Google AlphaEarth (Satellite Embedding dataset)

A DeepMind geospatial foundation model. Google ran it at planetary scale and published the output: for every 10 m by 10 m land pixel on Earth, for every year since 2017, a 64-dimensional embedding vector that compresses a full year of multi-sensor satellite observation (Sentinel-2 optical, Landsat, radar, elevation, climate). Available free in Google Earth Engine as an analysis-ready image collection, and as Cloud Optimized GeoTIFFs on GCS and AWS. The embeddings plug directly into simple downstream models: classification, regression, similarity search, change detection. No GPU, no fine-tuning of the foundation model itself.

**What you use it for (this is your strongest ML story):**
1. **Land suitability classification.** Train a small classifier on the embeddings to label pixels as buildable (flat, cleared or industrial, not water, not forest, not dense urban).
2. **Similarity search.** Take the mean embedding of pixels at known hyperscale data center sites and find the most similar land elsewhere in Europe. "Show me land that looks like the land under existing data centers" is a one-line demo with a foundation model behind it.
3. **Feature input.** Aggregate embeddings per candidate cell and feed them as features into the siting model (Section 4.3).

This is the differentiator. Most teams will do a weighted scoring map. Very few will use a geospatial foundation model correctly. Earth Engine has a free non-commercial tier; register a project before the hackathon.

### 2.6 One additional source worth adding

ENTSO-E Transparency Platform (free API key) for cross-border physical flows and zonal load if you want a live congestion feel. Ember already repackages the prices, so this is optional. Electricity Maps has hourly carbon intensity per zone but the free tier is limited; Ember monthly carbon intensity plus an hourly approximation from the generation mix is sufficient and fully open.

---

## 3. What You Are Building: Product Definition

**Name:** Loadstar (lodestar = guiding star; load = what a data center is to the grid).

**One sentence:** A decision support system that, for a data center of any given size, ranks European locations on price, carbon, grid headroom, and connectivity, optimizes the power supply mix for any chosen site, and lets the user interrogate every recommendation through a map and a conversational agent.

**The demo flow you are building toward (rehearse this):**
1. User types or says: "I want to build a 200 MW AI training campus in Europe. Carbon matters more than latency."
2. Agent parses requirements, calls the site search tool, and the map highlights the top 10 candidate cells with scores.
3. User clicks Tier 1 candidate (for example a cell in northern Sweden) and asks "compare this with Frankfurt."
4. Agent calls the comparison tool and explains: Sweden wins on price (around 30 EUR/MWh vs 80+), carbon (under 30 vs around 350 gCO2/kWh), and grid headroom; Frankfurt wins on fiber (DE-CIX is the largest internet exchange in the world) and latency to users. For a training workload, latency barely matters, so Sweden dominates.
5. User asks "how would I power it in Sweden?" Agent calls the supply mix optimizer, which returns a Pareto frontier of cost vs carbon and a recommended portfolio (for example 55% grid, 30% wind PPA, 10% on-site solar, 5% battery-shifted) with hourly dispatch charts.
6. Map overlay toggles show price, carbon, congestion, and the composite score across Europe.

Every step in that flow maps to one of the three "Worth Exploring" bullets. That is intentional.

---

## 4. System Architecture

### 4.1 High-level layout

```
┌──────────────────────────────────────────────────────────────┐
│  FRONTEND (Next.js + MapLibre GL / deck.gl)                  │
│  Map with toggleable layers │ Site detail panel │ Chat panel │
│  Pareto chart │ Hourly dispatch chart │ Assumptions panel    │
└───────────────▲──────────────────────────────▲───────────────┘
                │ REST / WebSocket             │
┌───────────────┴──────────────────────────────┴───────────────┐
│  API LAYER (FastAPI)                                         │
│  /sites/search  /sites/{id}  /sites/compare                  │
│  /optimize/supply-mix  /layers/{name}  /chat                 │
└───────▲───────────────▲──────────────────▲───────────────────┘
        │               │                  │
┌───────┴─────┐ ┌───────┴────────┐ ┌───────┴────────────────┐
│ SCORING &   │ │ OPTIMIZATION   │ │ AGENT LAYER            │
│ ML ENGINE   │ │ ENGINE         │ │ Claude + tool calling  │
│ H3 features │ │ PyPSA / linopy │ │ RAG over IEA report    │
│ LightGBM    │ │ LP per site    │ │ Tools = the API itself │
│ siting model│ │ Pareto sweep   │ │                        │
└───────▲─────┘ └───────▲────────┘ └────────────────────────┘
        │               │
┌───────┴───────────────┴──────────────────────────────────────┐
│  DATA LAYER (PostgreSQL + PostGIS, files in Parquet/NetCDF)  │
│  Offline ingestion pipeline (run BEFORE the hackathon):      │
│  • PyPSA-Eur prebuilt network + solved OPF results           │
│  • Ember API: hourly prices, carbon intensity, gen mix       │
│  • OSM/Overpass: substations, lines, IXPs, water, exclusions │
│  • AlphaEarth embeddings (Earth Engine export per H3 cell)   │
│  • Renewable capacity factor time series (from PyPSA-Eur     │
│    cutouts or renewables.ninja)                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Data layer and feature engineering

**Spatial unit: Uber H3 hexagons at resolution 5** (cells of roughly 250 km², about 9,000 cells covering Europe). Resolution 5 is coarse enough to precompute everything for the whole continent and fine enough to distinguish "near Stockholm" from "northern Sweden." Use resolution 6 or 7 only for zoomed-in refinement if time permits.

**Per-cell feature table (precomputed offline, stored in PostGIS):**

| Feature | Source | Notes |
|---|---|---|
| mean_price_eur_mwh | Ember hourly prices, ENTSO-E for multi-zone countries | Last 12 months. Critical fix: Ember publishes per country, but Sweden (SE1–SE4), Norway, Italy and Denmark have multiple bidding zones with very different prices. Pull zone-level day-ahead prices from ENTSO-E for those countries, otherwise the flagship "northern Sweden" recommendation rests on the wrong number (SE1 is far cheaper than SE4) |
| price_volatility | Ember | Std dev of hourly price; matters for flexible loads |
| carbon_intensity_g_kwh | Ember | Monthly, averaged; hourly approximation from gen mix |
| dist_hv_substation_km | OSM | Nearest substation with voltage >= 220 kV |
| substation_headroom_proxy | PyPSA-Eur | Free capacity at nearest network node after OPF |
| congestion_index | PyPSA-Eur OPF | Mean loading of lines incident to nearest node, plus nodal price spread vs zonal mean |
| dist_ixp_km | OSM / PeeringDB list | Distance to nearest internet exchange point |
| latency_proxy_ms | derived | Geodesic distance to nearest of FLAP-D metros × 0.01 ms/km × routing factor 1.5 |
| solar_cf, wind_cf | PyPSA-Eur cutouts | Mean annual capacity factors |
| water_dist_km | OSM | Nearest major river or lake |
| cooling_degree_proxy | climate normals | Mean summer temperature (free cooling potential) |
| buildable_fraction | AlphaEarth classifier | Share of cell pixels classified buildable |
| dc_similarity | AlphaEarth | Cosine similarity of cell mean embedding to mean embedding of known DC sites |
| exclusion_flag | OSM | Protected area, airport, floodplain overlap |

Build this table with a Python pipeline (geopandas, h3-py, osmnx or raw Overpass, requests for Ember, the earthengine-api for AlphaEarth). Run it once before the hackathon and commit the resulting Parquet (a few MB at res 5). During the event you only serve and model, never re-ingest. This is the single most important de-risking move.

### 4.3 ML component (the part that makes it more than a weighted map)

**Model 1: Siting propensity model.**
- **Labels:** positive = H3 cells containing existing large data centers (OSM tags, plus a curated list of known hyperscale sites: Dublin, Frankfurt, Amsterdam, Eemshaven, Luleå, Odense, Hamina, Paris, London, Madrid, Milan; 100 to 300 positives is plenty). Negatives = randomly sampled non-excluded cells (3 to 5 negatives per positive).
- **Features:** the table above, including the 64 AlphaEarth embedding dimensions aggregated per cell.
- **Model:** LightGBM binary classifier. Small, fast, gives SHAP values.
- **Output:** P(viable site). This captures factors your hand-tuned weights miss, and SHAP gives per-site explanations ("this cell scores high mainly because of substation proximity and land similarity to existing sites"), which feeds directly into the agent's explanations.
- **Honest framing for the interview:** this learns where data centers *have been* built (fiber-era logic). You combine it with the forward-looking score below precisely because past siting overweights connectivity and underweights power, and the constraint has flipped. Knowing and saying this is worth more than the model itself.

**Model 2: AlphaEarth land suitability classifier.**
- In Earth Engine: sample embeddings at hand-labeled points (industrial/cleared/flat = suitable; forest, water, dense urban, steep = unsuitable; 200 to 500 points, an hour of clicking, or bootstrap labels from ESA WorldCover classes). Train Earth Engine's built-in random forest on the 64 bands. Export per-cell suitable fraction. This is the "foundation model in production" line in your pitch.

**Composite score (the transparent layer users control):**

```
Score(cell) = w_price · norm(−price)
            + w_carbon · norm(−carbon_intensity)
            + w_cong · norm(−congestion_index)
            + w_dist · norm(−dist_substation)
            + w_conn · norm(−latency_proxy)
            + w_land · buildable_fraction
            + w_ml · P_viable(LightGBM)
subject to exclusion_flag = 0 and headroom_proxy ≥ requested_MW
```

Keep every term additive. An earlier draft multiplied congestion and substation distance inside one grid term; do not do that, because multiplication makes the score non-monotone in the weights, hides which factor drove a low score, and breaks the SHAP-style explanation story. Two separate weights keep the model transparent and the sliders honest.

Weights default to a sensible profile and are exposed as sliders / agent parameters ("carbon matters more than latency" → agent raises w_carbon, lowers w_conn, reruns). Normalize each feature to [0,1] across Europe (min-max or percentile). The hard headroom constraint is what makes "for a given data-center size" real: a 50 MW site list and a 500 MW site list differ because few nodes can absorb 500 MW.

### 4.4 Supply mix optimization engine (deliverable 2)

This is a linear program per site. Formulate it in PyPSA (a single-bus network) or linopy/PuLP directly. PyPSA is preferable because you can name-drop it credibly and it handles storage dynamics for you.

**Given:** site, load L (MW, assume flat 24/7 at PUE-adjusted draw, for example 200 MW IT × 1.2 PUE = 240 MW; offer a "flexible 10%" toggle), and one representative year of hourly data for that site: grid price p_t (Ember/ENTSO-E), grid carbon intensity c_t, solar capacity factor s_t, wind capacity factor w_t. Construct c_t explicitly rather than hand-waving: take the zone's hourly generation mix from ENTSO-E and multiply each technology's share by a standard emission factor (Ember's methodology document publishes these), or as a coarser fallback repeat Ember's monthly carbon intensity across the hours of each month. Document which method you used in ASSUMPTIONS.md, because hourly carbon is exactly the kind of number a domain judge will probe.

**Decision variables:** grid import g_t; PPA contracted capacities K_wind, K_solar (offtake = K × cf_t at fixed PPA strike price); on-site solar capacity; battery power and energy capacity with charge/discharge variables; optional on-site gas capacity for firmness; curtailment.

**Constraints:** hourly energy balance (supply = load every hour); battery state of charge dynamics and limits; grid connection limit (the site's headroom); optional carbon cap or renewable share floor.

**Objective:** minimize annualized cost = Σ g_t·p_t + PPA payments + annualized capex of on-site assets (use standard assumptions: solar around 600 EUR/kW, battery around 250 EUR/kWh, gas around 800 EUR/kW, WACC 7%, document all of them in the assumptions panel).

**Pareto frontier:** solve repeatedly while sweeping the carbon cap from unconstrained down to near zero (8 to 12 points). Plot cost (EUR/MWh effective) vs carbon (gCO2/kWh effective). This single chart answers "plan a supply mix of grid, PPA and on-site generation against cost and carbon" completely, and it demos beautifully: the user drags a carbon slider and watches the portfolio recompose.

**Load profile honesty:** a flat 24/7 load is the standard simplification, but the IEA specifically flags that AI training loads have rapid, large power swings, which is why on-site batteries are becoming standard. Add one sentence to the demo and the assumptions panel acknowledging this, and if time permits offer a second load profile option (flat vs a synthetic spiky training profile) so the battery in the optimal portfolio has a visible job beyond price arbitrage. This turns a known weakness into a feature toggle.

A 8760-hour LP with ~10 variables per hour solves in seconds with HiGHS (open source, ships with PyPSA). Cache results keyed on (site, load, constraints).

**Also report:** hourly matched carbon-free energy share (the 24/7 CFE metric Google popularized) vs annual-matched share. Distinguishing these two is an instant credibility signal with energy people.

### 4.5 Agent layer (the "help someone reason" requirement)

A single LLM agent (Claude via API) with tool calling. Do not over-engineer a multi-agent system; one agent with five clean tools is more reliable and easier to demo. If you want the multi-agent narrative for the pitch, frame the tools as specialist capabilities (siting analyst, power planner, grid analyst) orchestrated by one reasoner.

**Tools (each is just one of your API endpoints):**
1. `search_sites(power_mw, weights, region_filter, top_k)` → ranked cells with scores and feature breakdown.
2. `get_site_details(cell_id)` → all features, SHAP explanation, nearest substation and IXP.
3. `compare_sites(cell_ids)` → side-by-side table.
4. `optimize_supply_mix(cell_id, load_mw, carbon_cap?, flexibility?)` → portfolio, costs, dispatch summary, Pareto point.
5. `lookup_context(query)` → RAG retrieval over the IEA Energy and AI report (and your assumptions doc) for qualitative questions.

**System prompt rules that matter:** every number in an answer must come from a tool result; always state the top trade-off, not just the winner; state assumptions when giving costs; if the user's requirements are underspecified (no size, no workload type), ask one clarifying question. Workload type matters: training workloads are latency-tolerant (remote cheap clean sites win), inference serving is latency-sensitive (metro proximity matters), and the agent should reason about this distinction explicitly.

**Grounding check:** after generation, verify cited numbers appear in tool outputs (simple string/value match). Cheap to implement, and "we check the agent's numbers against the engine" is a strong answer to the inevitable hallucination question.

### 4.6 Frontend

- Next.js (or plain Vite + React), MapLibre GL with deck.gl H3HexagonLayer for the cell layers.
- Layer toggles: price, carbon, congestion, connectivity, composite score, ML propensity, exclusions. This is deliverable 3 in one component.
- Click a cell → detail drawer (features, SHAP bar chart, "optimize supply mix" button).
- Chat panel docked right; agent tool calls visibly echoed ("searching sites...", "running optimizer...") so judges see the system working.
- Serve cell geometries as GeoJSON for res 5 (small enough); switch to vector tiles (tippecanoe → PMTiles) only if you go finer.

### 4.7 Why these technology choices (anticipated interview questions)

- **Why H3, not raw polygons or a raster?** Uniform-ish cells, fast spatial joins, multi-resolution hierarchy for zoom refinement, trivial to serve.
- **Why LightGBM, not a deep model?** A few hundred labels; gradient boosting is the correct tool, trains in seconds, explains itself via SHAP. The deep learning is already done inside AlphaEarth; you consume its embeddings. Right-sizing models is the senior-engineer answer.
- **Why LP, not RL or heuristics?** Supply mix planning is a convex cost minimization with linear constraints. LP gives the provably optimal answer in seconds with full interpretability. Reaching for RL here would be a red flag.
- **Why one agent, not a swarm?** Reliability under demo conditions, simpler failure modes, lower latency. Tools are the modularity boundary, not agents.
- **Why precomputed features?** Siting fundamentals change monthly, not per request. Precompute heavy, serve light. This is also the core of the scaling story.

---

## 5. Evaluation (judges will ask "how do you know it works")

### 5.1 Siting model
- **Spatial holdout:** train the LightGBM on positives excluding two countries, test on them. Report AUC and precision@k.
- **Face validity ranking:** does the composite score rank known hubs and known announced expansion regions (Nordics, Iberia) sensibly under different weight profiles? Show that with carbon-heavy weights the Nordics dominate and with connectivity-heavy weights FLAP-D dominates. The system reproducing known industry behavior under the right weights is your strongest validity argument.
- **Sensitivity analysis:** perturb weights ±20%, report rank stability of the top 10 (Spearman correlation). Stable top tier = robust recommendation.

### 5.2 Supply mix optimizer
- **Baseline comparison:** grid-only portfolio vs optimized portfolio at equal carbon, and at equal cost. Headline number: "X% cost reduction at equal emissions, Y% emissions reduction at equal cost."
- **Backtest:** optimize on year N hourly prices, evaluate the fixed portfolio on year N+1 prices (Ember has multi-year hourly data). Shows the plan is not overfit to one price year.
- **Sanity invariants:** energy balance closes every hour; battery SoC never violated; shadow prices behave (tightening the carbon cap never lowers cost).

### 5.3 Agent
- A golden set of 15 to 20 question-answer pairs (siting, comparison, supply mix, conceptual). Score tool-call correctness (right tool, right arguments) and numeric faithfulness (every number traceable to tool output). Even a manual table of results in the README signals engineering maturity.

### 5.4 Honest limitations (say these before they ask)
- Congestion is a proxy from a clustered model, not actual TSO interconnection queue data (which is not open).
- Carbon intensity is country-level average; nodal marginal emissions would be better.
- Fiber data in OSM is incomplete; connectivity uses IXP and metro distance proxies.
- Land prices, permitting timelines, water rights, and local politics are out of scope; in reality permitting is often the longest pole.
- PPA prices are modeled at fixed strikes, not live market quotes.

Naming limitations precisely demonstrates domain understanding better than hiding them.

---

## 6. Scalability (explicitly requested, so dedicate a pitch slide to it)

**Data scale.**
- Resolution ladder: res 5 (~9k cells) for the continent → res 7 (~440k) for shortlisted regions → AlphaEarth native 10 m only for final parcels. Compute follows attention; you never process the planet at 10 m.
- Ingestion as scheduled batch jobs (Prefect or Airflow): Ember daily, OSM weekly, AlphaEarth and PyPSA-Eur OPF yearly. Feature store in PostGIS/Parquet; everything is rebuildable from sources.

**Serving scale.**
- Stateless FastAPI behind a load balancer; horizontal scaling is trivial because all heavy state is precomputed.
- Map layers as static vector tiles (PMTiles on a CDN), so map load costs the backend nothing.
- Optimizer runs in a Celery/RQ worker pool with result caching; identical (site, load, constraints) requests hit cache. Pareto sweeps parallelize per carbon-cap point.
- Agent layer scales with the LLM provider; the tools are the same cached endpoints.

**Geographic scale.**
- The architecture is region-agnostic: a region = one adapter set (prices, carbon, grid). Europe ships first because the open data is best. US = EIA + FERC queue data + utility LMPs; the H3 features, models, optimizer, and agent are unchanged. AlphaEarth is already global.

**Fidelity scale (the roadmap slide).**
- Swap congestion proxy for TSO interconnection queue and hosting capacity data where published.
- Hourly nodal carbon via Electricity Maps or marginal emissions modeling.
- Stochastic optimization over multiple weather and price years instead of one representative year.
- Permitting and land price layers from national cadastral data.

---

## 7. Build Plan

### 7.1 Before the hackathon (do as much as the rules allow; data prep is usually allowed)
1. Register: Ember API key, Google Earth Engine project, ENTSO-E key (optional), Anthropic API key.
2. Download the PyPSA-Eur prebuilt network; solve a 50 to 100 node clustered OPF once; save line loadings and nodal prices.
3. Run the ingestion pipeline; commit the per-cell feature Parquet.
4. Export AlphaEarth per-cell mean embeddings for Europe at res 5 from Earth Engine (one reduceRegions export job).
5. Curate the positive label list of existing data center sites.
6. Skeleton repo: FastAPI app, Next.js map showing the score layer from Parquet, chat panel stub.

### 7.2 During the hackathon (assuming ~24 to 36 hours, two to three people or solo with cuts)

| Block | Hours | Work |
|---|---|---|
| 1 | 0–3 | Wire feature Parquet → PostGIS → /layers endpoints → map renders all overlay toggles. **Deliverable 3 done early.** |
| 2 | 3–7 | Composite score + headroom constraint + /sites/search; train LightGBM + SHAP; site detail drawer. **Deliverable 1 done.** |
| 3 | 7–13 | Supply mix LP in PyPSA single-bus; Pareto sweep; dispatch and frontier charts. **Deliverable 2 done.** |
| 4 | 13–18 | Agent: 5 tools, system prompt, grounding check, RAG over IEA report (a few hundred chunks, any vector store, even in-memory). |
| 5 | 18–22 | Evaluation runs: holdout AUC, baseline comparison numbers, golden agent set. Put numbers in the README. |
| 6 | 22–26 | Polish: demo script rehearsal, assumptions panel, limitations slide, screenshots. |
| Buffer | 26+ | Stretch: res 7 zoom refinement, AlphaEarth similarity search demo, flexible-load toggle in the LP. |

**If time collapses, cut in this order:** RAG (agent can answer conceptually without it) → ML model (composite score alone still satisfies deliverable 1) → battery in the LP (grid + PPA + solar still satisfies deliverable 2). Never cut the map overlays or the Pareto chart; they are the two visuals that carry the demo.

### 7.3 Repository structure

```
loadstar/
├── data/                  # committed Parquet features, solved OPF NetCDF
├── pipeline/              # ingestion scripts (ember.py, osm.py, alphaearth.py, pypsa_opf.py)
├── ml/                    # train_siting.py, suitability labels, SHAP export
├── engine/                # scoring.py, supply_mix.py (PyPSA LP), pareto.py
├── api/                   # FastAPI app, routers, agent/ (tools, prompts, grounding)
├── web/                   # Next.js frontend
├── eval/                  # holdout eval, backtest, golden agent set + results
├── ASSUMPTIONS.md         # every cost, WACC, PUE, proxy definition, source
└── README.md              # architecture diagram, eval numbers, limitations, run instructions
```

---

## 8. Pitch Structure (5 minutes)

1. **Problem (30 s):** AI demand doubling to ~945 TWh by 2030; power has replaced fiber as the binding siting constraint; siting is a four-way trade-off nobody can hold in their head.
2. **Live demo (3 min):** the exact flow from Section 3. Map overlays → 200 MW carbon-weighted search → Sweden vs Frankfurt comparison with the agent's explanation → supply mix Pareto with the carbon slider.
3. **How it works (60 s):** one architecture slide. Name the stack: PyPSA-Eur for grid and congestion, Ember for hourly prices and carbon, OSM for infrastructure, AlphaEarth embeddings + LightGBM for land and siting, an LP for the portfolio, Claude with grounded tools on top. One sentence on evaluation numbers, one on scaling (precompute heavy, serve light, region = adapter).
4. **Limitations and roadmap (30 s):** queue data, nodal carbon, permitting. Shows you know where the demo ends and the product begins.

---

## 9. Glossary (be fluent in all of these)

- **PPA**: Power Purchase Agreement; long-term contract to buy a generator's output at a fixed strike price, the main instrument for corporate clean energy procurement.
- **Day-ahead / wholesale price**: hourly auction price per bidding zone; the marginal cost signal you optimize against.
- **Bidding zone**: the price area (mostly one per European country; Sweden has four, SE1 to SE4, with the cheap power in the north).
- **LMP / nodal price**: locational marginal price; price at a specific network node. Spread between nodal and zonal price indicates congestion.
- **OPF**: optimal power flow; the optimization that dispatches generators subject to network limits. Linearized (DC) OPF is what PyPSA-Eur solves.
- **Capacity factor**: actual output / nameplate output; ~10 to 13% for German solar, ~30 to 45% for good onshore/offshore wind.
- **Grid headroom / hosting capacity**: spare capacity at a connection point to absorb new load without upgrades.
- **Interconnection queue**: the waiting list for grid connections; multi-year in hot markets, the real-world bottleneck your congestion index proxies.
- **PUE**: Power Usage Effectiveness; total facility power / IT power. Modern hyperscale ~1.1 to 1.3.
- **24/7 CFE**: carbon-free energy matched hour by hour, vs annual matching where surplus midday solar "offsets" coal-powered nights on paper.
- **FLAP-D**: Frankfurt, London, Amsterdam, Paris, Dublin; Europe's connectivity-rich, grid-constrained data center hubs.
- **H3**: Uber's hexagonal hierarchical spatial index.
- **SHAP**: per-prediction feature attribution for tree models; your explanation mechanism.

---

## 10. Final Checklist

- [ ] All API keys registered and tested before the event
- [ ] Feature Parquet built and committed; no live ingestion during the hackathon
- [ ] PyPSA-Eur OPF pre-solved; results file in repo
- [ ] AlphaEarth embeddings exported per cell
- [ ] Demo flow rehearsed end to end at least twice
- [ ] Eval numbers (AUC, baseline savings, agent faithfulness) in the README
- [ ] ASSUMPTIONS.md complete with sources
- [ ] Limitations slide written
- [ ] Fallback: recorded demo video in case of live failure
