# External Source Access Decisions

Generated at: `2026-06-12T21:17:02+00:00`

This file is a decision record for issue 2. It records not only source status, but also what each status implies downstream.

| Source | Status | Check | Evidence | Downstream implication | Fallback |
|---|---|---|---|---|---|
| Google Earth Engine / AlphaEarth | `blocked` | EARTHENGINE_PROJECT is not configured, so an AlphaEarth embedding sample cannot run. | Missing EARTHENGINE_PROJECT. | Issues 9 and 10 must proceed without AlphaEarth-derived features until approval/access is available. | Use non-embedding land features and transparent scoring; omit `buildable_fraction` model output if needed. |
| Ember hourly electricity prices | `blocked` | No EMBER_HOURLY_PRICE_URL was configured for an actual hourly price pull. | Root endpoint probe returned HTTP 404; hourly data endpoint not verified. | Issue 6 must not assume Ember hourly price access. Use a verified endpoint or fallback before replacing fixture prices. | Use checked fixture prices or ENTSO-E-backed prices with provisional labels. |
| ITU BBmaps | `fallback` | Confirmed public ITU transmission map page is reachable, but no feature extraction URL was configured. | HTTP 200; final_url=https://www.itu.int/en/ITU-D/Technology/Pages/InteractiveTransmissionMaps.aspx | Issue 6 should ingest IXP distances instead, and issue 8 should label connectivity as an IXP/connectivity proxy until BBmaps extraction is available. | Use OSM/PeeringDB IXP distance proxy for `dist_ixp_km`; keep `dist_fiber_km` flagged as provisional. |
| Zenodo PyPSA-Eur record 18619025 | `ok` | Fetched record metadata and confirmed buses.csv and lines.csv artifacts. | HTTP 200; files=buses.csv, converters.csv, lines.csv, links.csv, map.html, transformers.csv | Issue 6 can download the PyPSA-Eur OSM network and produce the OPF artifact. |  |
