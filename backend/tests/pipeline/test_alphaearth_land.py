import json
import sqlite3
from pathlib import Path

from backend.pipeline.alphaearth_land import run_alphaearth_land_model


def test_alphaearth_land_fallback_outputs_values_metrics_and_metadata(tmp_path: Path) -> None:
    output_dir = tmp_path / "processed"
    eval_dir = tmp_path / "eval"
    metadata_database = tmp_path / "source_artifacts.db"

    result = run_alphaearth_land_model(
        countries="SE,DE,IE",
        output_dir=output_dir,
        eval_dir=eval_dir,
        metadata_database=metadata_database,
        earthengine_project=None,
    )

    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))

    assert result.record_count == 10
    assert payload["source_status"] == "fallback"
    assert payload["active_method"] == "fixture_land_proxy"
    assert payload["deterministic_seed"] == 20260612
    assert {record["country_code"] for record in payload["records"]} == {"SE", "DE", "IE"}
    for record in payload["records"]:
        assert 0 <= record["buildable_fraction"] <= 1
        assert 0 <= record["dc_similarity"] <= 1
        assert record["source_method"] == "fixture_land_proxy"

    assert metrics["source_status"] == "fallback"
    assert metrics["label_summary"]["heldout_count"] > 0
    assert metrics["label_summary"]["buildable_positive_count"] > 0
    assert metrics["label_summary"]["buildable_negative_count"] > 0
    assert metrics["heldout_metrics"]["buildable_accuracy"] is not None
    assert metrics["heldout_labels"]
    assert metrics["manual_map_checks"]
    assert all(check["status"] == "not_performed" for check in metrics["manual_map_checks"])

    with sqlite3.connect(metadata_database) as connection:
        row = connection.execute(
            """
            SELECT checksum_sha256, record_count, source_status, fallback
            FROM source_artifacts
            WHERE artifact_name = 'alphaearth_land_subset'
            AND country_scope = 'SE,DE,IE'
            """
        ).fetchone()

    assert row == (
        result.checksum_sha256,
        10,
        "fallback",
        "Earth Engine project or package unavailable; using fixture land proxy.",
    )
