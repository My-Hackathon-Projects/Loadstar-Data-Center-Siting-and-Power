CREATE TABLE IF NOT EXISTS h3_cells (
    cell_id TEXT PRIMARY KEY,
    geom_geojson TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    country_code TEXT NOT NULL,
    region_name TEXT NOT NULL,
    resolution INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS site_features (
    cell_id TEXT PRIMARY KEY REFERENCES h3_cells(cell_id),
    mean_price_eur_mwh REAL NOT NULL,
    price_volatility REAL NOT NULL,
    carbon_intensity_g_kwh REAL NOT NULL,
    congestion_index REAL NOT NULL,
    headroom_mw REAL NOT NULL,
    dist_hv_substation_km REAL NOT NULL,
    dist_fiber_km REAL NOT NULL,
    dist_ixp_km REAL NOT NULL,
    latency_proxy_ms REAL NOT NULL,
    solar_cf REAL NOT NULL,
    wind_cf REAL NOT NULL,
    water_dist_km REAL NOT NULL,
    cooling_degree_proxy REAL NOT NULL,
    buildable_fraction REAL NOT NULL,
    dc_similarity REAL NOT NULL,
    lightgbm_score REAL NOT NULL,
    shap_values_json TEXT NOT NULL,
    exclusion_flag INTEGER NOT NULL DEFAULT 0,
    feature_version TEXT NOT NULL DEFAULT 'fixture-v1',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hourly_energy (
    -- INTEGER PRIMARY KEY auto-increments via SQLite ROWID and is the
    -- portable form: in Postgres, swap to BIGSERIAL during the live-DB switch.
    id INTEGER PRIMARY KEY,
    zone_id TEXT NOT NULL,
    timestamp_utc TEXT NOT NULL,
    price_eur_mwh REAL NOT NULL,
    carbon_g_kwh REAL NOT NULL,
    solar_cf REAL NOT NULL,
    wind_cf REAL NOT NULL,
    source_method TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(zone_id, timestamp_utc)
);

CREATE TABLE IF NOT EXISTS optimization_runs (
    run_id TEXT PRIMARY KEY,
    cell_id TEXT NOT NULL REFERENCES h3_cells(cell_id),
    load_mw REAL NOT NULL,
    request_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    cache_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
