-- Postgres equivalent of 001_initial.sql.
-- Same column names, types, NULL/UNIQUE constraints, default expressions; only
-- the surrogate key on hourly_energy and the timestamp default differ between
-- the SQLite (001_initial.sql) and the Postgres path. Migration tooling picks
-- the right file at runtime based on `database_url` scheme.

CREATE TABLE IF NOT EXISTS h3_cells (
    cell_id TEXT PRIMARY KEY,
    geom_geojson TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    country_code TEXT NOT NULL,
    region_name TEXT NOT NULL,
    resolution INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS site_features (
    cell_id TEXT PRIMARY KEY REFERENCES h3_cells(cell_id),
    mean_price_eur_mwh DOUBLE PRECISION NOT NULL,
    price_volatility DOUBLE PRECISION NOT NULL,
    carbon_intensity_g_kwh DOUBLE PRECISION NOT NULL,
    congestion_index DOUBLE PRECISION NOT NULL,
    headroom_mw DOUBLE PRECISION NOT NULL,
    dist_hv_substation_km DOUBLE PRECISION NOT NULL,
    dist_fiber_km DOUBLE PRECISION NOT NULL,
    dist_ixp_km DOUBLE PRECISION NOT NULL,
    latency_proxy_ms DOUBLE PRECISION NOT NULL,
    solar_cf DOUBLE PRECISION NOT NULL,
    wind_cf DOUBLE PRECISION NOT NULL,
    water_dist_km DOUBLE PRECISION NOT NULL,
    cooling_degree_proxy DOUBLE PRECISION NOT NULL,
    buildable_fraction DOUBLE PRECISION NOT NULL,
    dc_similarity DOUBLE PRECISION NOT NULL,
    lightgbm_score DOUBLE PRECISION NOT NULL,
    shap_values_json TEXT NOT NULL,
    exclusion_flag INTEGER NOT NULL DEFAULT 0,
    feature_version TEXT NOT NULL DEFAULT 'fixture-v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hourly_energy (
    -- Postgres uses BIGSERIAL where SQLite uses INTEGER PRIMARY KEY (ROWID).
    id BIGSERIAL PRIMARY KEY,
    zone_id TEXT NOT NULL,
    timestamp_utc TIMESTAMPTZ NOT NULL,
    price_eur_mwh DOUBLE PRECISION NOT NULL,
    carbon_g_kwh DOUBLE PRECISION NOT NULL,
    solar_cf DOUBLE PRECISION NOT NULL,
    wind_cf DOUBLE PRECISION NOT NULL,
    source_method TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(zone_id, timestamp_utc)
);

CREATE TABLE IF NOT EXISTS optimization_runs (
    run_id TEXT PRIMARY KEY,
    cell_id TEXT NOT NULL REFERENCES h3_cells(cell_id),
    load_mw DOUBLE PRECISION NOT NULL,
    request_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    cache_key TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
