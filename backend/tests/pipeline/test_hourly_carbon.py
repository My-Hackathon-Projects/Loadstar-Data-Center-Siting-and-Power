import hashlib
import json
import sqlite3
from pathlib import Path

from backend.pipeline.hourly_carbon import (
    TECH_EMISSION_FACTORS_G_KWH,
    run_hourly_carbon_ingestion,
)


def test_hourly_carbon_fallback_repeats_monthly_values_for_optimizer_zones(
    tmp_path: Path,
) -> None:
    result = run_hourly_carbon_ingestion(
        countries="SE,DE,IE",
        output_dir=tmp_path / "processed",
        metadata_database=tmp_path / "source_artifacts.db",
    )

    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert payload["active_method"] == "ember_monthly_repeat"
    assert result.record_count == 3 * 365 * 24

    se_january = [
        record["carbon_g_kwh"]
        for record in payload["records"]
        if record["zone_id"] == "SE" and record["month"] == 1
    ]
    assert len(se_january) == 31 * 24
    assert len(set(se_january)) == 1

    with sqlite3.connect(result.metadata_database) as connection:
        row = connection.execute(
            """
            SELECT artifact_name, checksum_sha256, source_status
            FROM source_artifacts
            WHERE artifact_name = 'hourly_carbon_subset'
            AND country_scope = 'SE,DE,IE'
            """
        ).fetchone()

    assert row == ("hourly_carbon_subset", result.checksum_sha256, "fallback")


def test_hourly_carbon_preferred_method_uses_entsoe_generation_mix(
    tmp_path: Path,
) -> None:
    entsoe_path = tmp_path / "entsoe_mix.json"
    entsoe_payload = {
        "records": [
            {
                "zone_id": "SE",
                "timestamp_utc": "2026-01-01T00:00:00+00:00",
                "generation_mix_mwh": {
                    "wind": 70,
                    "solar": 10,
                    "gas": 20,
                },
            }
        ]
    }
    entsoe_path.write_text(json.dumps(entsoe_payload), encoding="utf-8")

    result = run_hourly_carbon_ingestion(
        countries="SE",
        output_dir=tmp_path / "processed",
        metadata_database=tmp_path / "source_artifacts.db",
        entsoe_generation_mix=entsoe_path,
        method="entsoe",
    )
    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    record = payload["records"][0]
    expected = (
        70 * TECH_EMISSION_FACTORS_G_KWH["wind"]
        + 10 * TECH_EMISSION_FACTORS_G_KWH["solar"]
        + 20 * TECH_EMISSION_FACTORS_G_KWH["gas"]
    ) / 100

    assert payload["active_method"] == "entsoe_hourly_generation_mix"
    assert record["carbon_g_kwh"] == round(expected, 3)
    assert result.source_version.startswith("entsoe-generation-mix-sha256:")
    assert result.checksum_sha256 == hashlib.sha256(result.output_path.read_bytes()).hexdigest()
