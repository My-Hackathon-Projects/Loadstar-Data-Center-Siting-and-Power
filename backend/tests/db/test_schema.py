import sqlite3

from backend.db.migrate import apply_schema


def test_initial_schema_creates_only_four_product_tables(tmp_path) -> None:
    database_path = tmp_path / "loadstar.db"
    apply_schema(database_path)

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

    assert [row[0] for row in rows] == [
        "h3_cells",
        "hourly_energy",
        "optimization_runs",
        "site_features",
    ]


def test_initial_schema_accepts_fixture_shaped_site_features(tmp_path) -> None:
    database_path = tmp_path / "loadstar.db"
    apply_schema(database_path)

    geom_json = '{"type":"Point","coordinates":[22.1547,65.5848]}'
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO h3_cells (
                cell_id, geom_geojson, latitude, longitude, country_code, region_name, resolution
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("851f25d7fffffff", geom_json, 65.5848, 22.1547, "SE", "Lulea / Boden", 5),
        )
        connection.execute(
            """
            INSERT INTO site_features (
                cell_id, mean_price_eur_mwh, price_volatility, carbon_intensity_g_kwh,
                congestion_index, headroom_mw, dist_hv_substation_km, dist_fiber_km,
                dist_ixp_km, latency_proxy_ms, solar_cf, wind_cf, water_dist_km,
                cooling_degree_proxy, buildable_fraction, dc_similarity, lightgbm_score,
                shap_values_json, exclusion_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "851f25d7fffffff",
                34,
                17,
                24,
                0.22,
                540,
                7.2,
                18.4,
                710,
                14.8,
                0.10,
                0.42,
                3.4,
                0.18,
                0.72,
                0.81,
                0.79,
                '{"headroom_mw":0.22}',
                0,
            ),
        )
        count = connection.execute("SELECT COUNT(*) FROM site_features").fetchone()[0]

    assert count == 1
