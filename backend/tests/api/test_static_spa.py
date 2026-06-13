from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import main


def test_static_layer_json_route_does_not_shadow_live_layer_api(
    tmp_path: Path, monkeypatch
) -> None:
    dist_dir = tmp_path / "dist"
    layers_dir = dist_dir / "layers"
    layers_dir.mkdir(parents=True)
    (layers_dir / "composite_score.json").write_text('{"source":"static"}', encoding="utf-8")
    monkeypatch.setattr(main, "web_dist_dir", dist_dir)

    client = TestClient(main.app)

    static_response = client.get("/layers/composite_score.json")
    assert static_response.status_code == 200
    assert static_response.json() == {"source": "static"}

    live_response = client.get("/layers/composite_score")
    assert live_response.status_code == 200
    assert live_response.json()["cache_key"].startswith("layers:")


def test_spa_routes_return_index_without_masking_unknown_paths(
    tmp_path: Path, monkeypatch
) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<!doctype html><div id='root'></div>", encoding="utf-8")
    monkeypatch.setattr(main, "web_dist_dir", dist_dir)

    client = TestClient(main.app)

    spa_response = client.get("/app")
    assert spa_response.status_code == 200
    assert "root" in spa_response.text

    unknown_response = client.get("/not-an-api-route")
    assert unknown_response.status_code == 404
