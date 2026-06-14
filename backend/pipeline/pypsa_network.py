"""Real PyPSA-Eur ingestion: HV transmission grid + nearest-substation overlay.

Inputs: ``buses.csv``, ``lines.csv``, ``links.csv`` from PyPSA-Eur (Zenodo
record 18619025) placed under ``data/raw/pypsa_eur/``. The CSVs are the
HV/EHV (220-750 kV) European grid topology derived from OpenStreetMap.

Outputs:

* ``data/pypsa_network.db`` -- SQLite with ``pypsa_bus``, ``pypsa_line``,
  ``meta`` tables. Idempotent (DROP/CREATE inside one transaction).
* ``frontend/public/layers/transmission_grid.geojson`` -- single
  FeatureCollection with mixed Point + LineString geometries. Buses and
  lines below 220 kV are filtered out at build time; tier (``ehv`` >= 380
  kV, ``hv`` 220-380 kV) is precomputed so the SPA never re-bins.
* ``data/processed/subset/site_features_subset.json`` patched in place
  with three nearest-substation fields per site (kv, distance_km,
  capacity_mva). The new keys are additive; everything else is preserved.

The CLI also upserts a row into ``data/processed/source_artifacts.db`` so
``GET /meta/source-artifacts`` exposes the artifact alongside the others.

This module deliberately avoids ``pyproj``: at the SE/DE/IE latitudes we
care about, an equirectangular projection with a cosine correction at
the dataset's mean latitude has metre-scale error per kilometre, which
is irrelevant when picking the nearest substation among 7 k candidates.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, cast

import numpy as np
import typer
from scipy.spatial import cKDTree as _cKDTree  # type: ignore[reportMissingTypeStubs]

from backend.pipeline.artifacts import (
    ArtifactSummary,
    display_path,
    upsert_source_artifacts,
)
from backend.pipeline.constants import DEFAULT_COUNTRIES

# scipy.spatial has no py.typed stubs; alias the import through `cast(Any, ...)`
# so pyright stops complaining about every cKDTree return value being unknown.
cKDTree = cast(Any, _cKDTree)

ROOT_DIR = Path(__file__).resolve().parents[2]

RAW_DIR_DEFAULT = ROOT_DIR / "data" / "raw" / "pypsa_eur"
DB_DEFAULT = ROOT_DIR / "data" / "pypsa_network.db"
GEOJSON_DEFAULT = ROOT_DIR / "frontend" / "public" / "layers" / "transmission_grid.json"
SITE_FEATURES_DEFAULT = ROOT_DIR / "data" / "processed" / "subset" / "site_features_subset.json"
METADATA_DB_DEFAULT = ROOT_DIR / "data" / "processed" / "source_artifacts.db"

ARTIFACT_VERSION = "pypsa-network-v1"
ARTIFACT_NAME = "pypsa_network"
SOURCE_NAME = "Zenodo PyPSA-Eur record 18619025"

# Below 220 kV is filtered out at build time. PyPSA-Eur v0.7 already publishes
# only 220-750 kV but keep the floor explicit so a future sub-HV release does
# not silently leak into the GeoJSON.
MIN_VOLTAGE_KV: float = 220.0
EHV_THRESHOLD_KV: float = 380.0


@dataclass(frozen=True)
class Bus:
    bus_id: str
    voltage_kv: float
    country: str
    longitude: float
    latitude: float
    dc: bool


@dataclass(frozen=True)
class Edge:
    """Either an AC line or an HVDC link, normalized to a common shape."""

    edge_id: str
    bus0: str
    bus1: str
    voltage_kv: float
    capacity_mva: float
    length_km: float
    is_hvdc: bool


@dataclass(frozen=True)
class IngestionResult:
    raw_dir: Path
    database: Path
    geojson: Path
    site_features: Path | None
    bus_count: int
    line_count: int
    link_count: int
    rendered_bus_count: int
    rendered_edge_count: int
    overlay_updated: int


app = typer.Typer(add_completion=False, help="Ingest PyPSA-Eur HV grid and emit overlays.")


# ----- CSV parsing --------------------------------------------------------


def _to_float(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _truthy(value: str) -> bool:
    """PyPSA CSVs use 't'/'f' for booleans."""

    return value.strip().lower() in {"t", "true", "1"}


def read_buses(path: Path) -> list[Bus]:
    """Parse ``buses.csv``. Columns we care about: bus_id, voltage, dc, country, x, y.

    PyPSA-Eur ``x`` is longitude, ``y`` is latitude. The full ``geometry``
    column duplicates ``x``/``y`` and is ignored.
    """

    buses: list[Bus] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            voltage = _to_float(row.get("voltage", ""))
            x = _to_float(row.get("x", ""))
            y = _to_float(row.get("y", ""))
            country = (row.get("country") or "").strip().upper()
            bus_id = (row.get("bus_id") or "").strip()
            if voltage is None or x is None or y is None or not bus_id or not country:
                continue
            buses.append(
                Bus(
                    bus_id=bus_id,
                    voltage_kv=voltage,
                    country=country,
                    longitude=x,
                    latitude=y,
                    dc=_truthy(row.get("dc", "f")),
                )
            )
    return buses


def read_lines(path: Path) -> list[Edge]:
    """Parse ``lines.csv``: AC transmission lines.

    PyPSA-Eur convention: ``s_nom`` is in MVA, ``voltage`` is in kV, and
    ``length`` is in metres (NOT kilometres -- empirically the field is
    ~1000x the great-circle distance between bus endpoints). We convert
    to km so the GeoJSON property is consistent with the bus aggregates.
    """

    edges: list[Edge] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            line_id = (row.get("line_id") or "").strip()
            bus0 = (row.get("bus0") or "").strip()
            bus1 = (row.get("bus1") or "").strip()
            voltage = _to_float(row.get("voltage", ""))
            s_nom = _to_float(row.get("s_nom", ""))
            length_m = _to_float(row.get("length", ""))
            if not (line_id and bus0 and bus1) or voltage is None:
                continue
            edges.append(
                Edge(
                    edge_id=line_id,
                    bus0=bus0,
                    bus1=bus1,
                    voltage_kv=voltage,
                    capacity_mva=s_nom if s_nom is not None else 0.0,
                    length_km=(length_m / 1000.0) if length_m is not None else 0.0,
                    is_hvdc=False,
                )
            )
    return edges


def read_links(path: Path) -> list[Edge]:
    """Parse ``links.csv``: HVDC interconnectors.

    PyPSA-Eur stores HVDC capacity as ``p_nom`` (MW). For symmetry with AC
    lines we treat MW ~= MVA (HVDC unity power factor by convention here)
    and flag the edge with ``is_hvdc=True``. ``length`` is in metres,
    same as ``lines.csv``.
    """

    edges: list[Edge] = []
    if not path.exists():
        return edges
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            link_id = (row.get("link_id") or "").strip()
            bus0 = (row.get("bus0") or "").strip()
            bus1 = (row.get("bus1") or "").strip()
            voltage = _to_float(row.get("voltage", ""))
            p_nom = _to_float(row.get("p_nom", ""))
            length_m = _to_float(row.get("length", ""))
            if not (link_id and bus0 and bus1) or voltage is None:
                continue
            edges.append(
                Edge(
                    edge_id=f"link:{link_id}",
                    bus0=bus0,
                    bus1=bus1,
                    voltage_kv=voltage,
                    capacity_mva=p_nom if p_nom is not None else 0.0,
                    length_km=(length_m / 1000.0) if length_m is not None else 0.0,
                    is_hvdc=True,
                )
            )
    return edges


# ----- Aggregations -------------------------------------------------------


def _voltage_tier(voltage_kv: float) -> str:
    return "ehv" if voltage_kv >= EHV_THRESHOLD_KV else "hv"


def _bus_aggregates(
    edges: Sequence[Edge],
    buses_by_id: dict[str, Bus],
) -> dict[str, tuple[int, float]]:
    """Return ``{bus_id: (degree, connected_capacity_mva)}`` over edges that survive
    the HV filter (both endpoints are in ``buses_by_id`` and the edge voltage
    is >= ``MIN_VOLTAGE_KV``)."""

    degree: dict[str, int] = {}
    capacity: dict[str, float] = {}
    for edge in edges:
        if edge.voltage_kv < MIN_VOLTAGE_KV:
            continue
        if edge.bus0 not in buses_by_id or edge.bus1 not in buses_by_id:
            continue
        for endpoint in (edge.bus0, edge.bus1):
            degree[endpoint] = degree.get(endpoint, 0) + 1
            capacity[endpoint] = capacity.get(endpoint, 0.0) + edge.capacity_mva
    return {
        bus_id: (degree.get(bus_id, 0), round(capacity.get(bus_id, 0.0), 2))
        for bus_id in buses_by_id
    }


# ----- Persistence --------------------------------------------------------


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_database(
    database: Path,
    buses: Sequence[Bus],
    edges: Sequence[Edge],
    raw_files: Iterable[Path],
) -> None:
    """Persist HV-only buses + edges to SQLite. Idempotent across runs."""

    database.parent.mkdir(parents=True, exist_ok=True)
    rendered_edges = [e for e in edges if e.voltage_kv >= MIN_VOLTAGE_KV]
    bus_ids_with_edges = {e.bus0 for e in rendered_edges} | {e.bus1 for e in rendered_edges}
    rendered_buses = [
        b for b in buses if b.voltage_kv >= MIN_VOLTAGE_KV or b.bus_id in bus_ids_with_edges
    ]

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE IF EXISTS pypsa_bus")
        connection.execute("DROP TABLE IF EXISTS pypsa_line")
        connection.execute("DROP TABLE IF EXISTS meta")
        connection.execute(
            """
            CREATE TABLE pypsa_bus (
                bus_id TEXT PRIMARY KEY,
                voltage_kv REAL NOT NULL,
                country TEXT NOT NULL,
                longitude REAL NOT NULL,
                latitude REAL NOT NULL,
                dc INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE pypsa_line (
                edge_id TEXT PRIMARY KEY,
                bus0 TEXT NOT NULL,
                bus1 TEXT NOT NULL,
                voltage_kv REAL NOT NULL,
                capacity_mva REAL NOT NULL,
                length_km REAL NOT NULL,
                is_hvdc INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO pypsa_bus VALUES (?, ?, ?, ?, ?, ?)",
            [
                (b.bus_id, b.voltage_kv, b.country, b.longitude, b.latitude, int(b.dc))
                for b in sorted(rendered_buses, key=lambda b: b.bus_id)
            ],
        )
        connection.executemany(
            "INSERT INTO pypsa_line VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    e.edge_id,
                    e.bus0,
                    e.bus1,
                    e.voltage_kv,
                    e.capacity_mva,
                    e.length_km,
                    int(e.is_hvdc),
                )
                for e in sorted(rendered_edges, key=lambda e: e.edge_id)
            ],
        )
        meta_rows: list[tuple[str, str]] = [
            ("artifact_version", ARTIFACT_VERSION),
            ("min_voltage_kv", str(MIN_VOLTAGE_KV)),
            ("ehv_threshold_kv", str(EHV_THRESHOLD_KV)),
            ("rendered_bus_count", str(len(rendered_buses))),
            ("rendered_edge_count", str(len(rendered_edges))),
        ]
        for raw_file in sorted(raw_files):
            if raw_file.exists():
                meta_rows.append((f"sha256:{raw_file.name}", _file_sha256(raw_file)))
        connection.executemany("INSERT INTO meta VALUES (?, ?)", meta_rows)
        connection.commit()


# ----- GeoJSON emission ---------------------------------------------------


def _build_geojson_payload(
    buses: Sequence[Bus],
    edges: Sequence[Edge],
) -> dict[str, Any]:
    buses_by_id = {bus.bus_id: bus for bus in buses if bus.voltage_kv >= MIN_VOLTAGE_KV}
    rendered_edges = [
        edge
        for edge in edges
        if edge.voltage_kv >= MIN_VOLTAGE_KV
        and edge.bus0 in buses_by_id
        and edge.bus1 in buses_by_id
    ]
    aggregates = _bus_aggregates(rendered_edges, buses_by_id)

    bus_features: list[dict[str, Any]] = []
    for bus in sorted(buses_by_id.values(), key=lambda b: b.bus_id):
        degree, connected = aggregates.get(bus.bus_id, (0, 0.0))
        if degree == 0:
            # Drop islanded HV buses so the overlay stays signal not noise.
            continue
        bus_features.append(
            {
                "type": "Feature",
                "id": f"bus:{bus.bus_id}",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(bus.longitude, 6), round(bus.latitude, 6)],
                },
                "properties": {
                    "kind": "bus",
                    "bus_id": bus.bus_id,
                    "voltage_kv": bus.voltage_kv,
                    "country": bus.country,
                    "degree": degree,
                    "connected_capacity_mva": connected,
                },
            }
        )

    line_features: list[dict[str, Any]] = []
    for edge in sorted(rendered_edges, key=lambda e: e.edge_id):
        b0 = buses_by_id[edge.bus0]
        b1 = buses_by_id[edge.bus1]
        line_features.append(
            {
                "type": "Feature",
                "id": f"line:{edge.edge_id}",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [round(b0.longitude, 6), round(b0.latitude, 6)],
                        [round(b1.longitude, 6), round(b1.latitude, 6)],
                    ],
                },
                "properties": {
                    "kind": "line",
                    "line_id": edge.edge_id,
                    "voltage_kv": edge.voltage_kv,
                    "voltage_tier": _voltage_tier(edge.voltage_kv),
                    "capacity_mva": round(edge.capacity_mva, 2),
                    "length_km": round(edge.length_km, 2),
                    "is_hvdc": edge.is_hvdc,
                    "is_cross_border": b0.country != b1.country,
                    "country0": b0.country,
                    "country1": b1.country,
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "metadata": {
            "artifact_version": ARTIFACT_VERSION,
            "source": SOURCE_NAME,
            "min_voltage_kv": MIN_VOLTAGE_KV,
            "ehv_threshold_kv": EHV_THRESHOLD_KV,
            "bus_count": len(bus_features),
            "line_count": len(line_features),
        },
        "features": [*bus_features, *line_features],
    }


def write_geojson(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Compact: this overlay is a multi-megabyte machine artifact committed for
    # the Vercel static path (the SPA reads it, never edits it). `sort_keys`
    # keeps regeneration byte-deterministic so the committed file stays stable.
    content = json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ----- Nearest-substation overlay ----------------------------------------


def _project_to_meters(
    longitudes: np.ndarray,
    latitudes: np.ndarray,
    *,
    reference_latitude: float | None = None,
) -> np.ndarray:
    """Equirectangular projection with cosine correction at a reference latitude.

    Pass an explicit ``reference_latitude`` so the bus tree and the site
    points share the same projection centre -- otherwise each call would
    compute its own centre from its own array, and a site near a bus would
    project far apart purely because of cosine drift between the two
    centres. Good to ~1 m accuracy per km at SE/DE/IE latitudes.
    """

    if reference_latitude is None:
        reference_latitude = float(np.mean(latitudes)) if latitudes.size else 0.0
    earth_radius = 6_371_000.0
    lat_rad = np.deg2rad(latitudes)
    lon_rad = np.deg2rad(longitudes)
    cos_ref = math.cos(math.radians(reference_latitude))
    x = earth_radius * lon_rad * cos_ref
    y = earth_radius * lat_rad
    return np.stack([x, y], axis=1)


def overlay_nearest_substation(
    site_features_path: Path,
    buses: Sequence[Bus],
    edges: Sequence[Edge],
) -> int:
    """Annotate ``site_features_subset.json`` in place with three new keys.

    Adds ``nearest_substation_kv``, ``nearest_substation_distance_km``, and
    ``nearest_substation_capacity_mva`` to each record. Only HV-and-above
    buses (>= 220 kV) participate, matching what the GeoJSON renders and
    what an operator could realistically interconnect to. Capacity is the
    sum of nominal MVA across all HV edges incident to the chosen bus.

    Idempotent: re-running with the same inputs produces the same values.
    Returns the number of records updated.
    """

    if not site_features_path.exists():
        return 0
    hv_buses = [bus for bus in buses if bus.voltage_kv >= MIN_VOLTAGE_KV]
    if not hv_buses:
        return 0

    buses_by_id = {bus.bus_id: bus for bus in hv_buses}
    aggregates = _bus_aggregates(edges, buses_by_id)

    longitudes = np.array([bus.longitude for bus in hv_buses])
    latitudes = np.array([bus.latitude for bus in hv_buses])
    reference_lat = float(np.mean(latitudes))
    bus_xy = _project_to_meters(longitudes, latitudes, reference_latitude=reference_lat)
    tree = cKDTree(bus_xy)

    payload_raw = json.loads(site_features_path.read_text(encoding="utf-8"))
    if not isinstance(payload_raw, dict):
        return 0
    payload = cast(dict[str, Any], payload_raw)
    raw_records = payload.get("records")
    if not isinstance(raw_records, list):
        return 0
    records = cast(list[dict[str, Any]], raw_records)

    if not records:
        return 0

    site_lons = np.array([float(r.get("longitude", 0.0)) for r in records])
    site_lats = np.array([float(r.get("latitude", 0.0)) for r in records])
    site_xy = _project_to_meters(site_lons, site_lats, reference_latitude=reference_lat)

    distances_m, indices = tree.query(site_xy, k=1)
    updated = 0
    for record, distance_m, idx in zip(records, distances_m, indices, strict=True):
        bus = hv_buses[int(idx)]
        _, connected = aggregates.get(bus.bus_id, (0, 0.0))
        record["nearest_substation_kv"] = float(bus.voltage_kv)
        record["nearest_substation_distance_km"] = round(float(distance_m) / 1000.0, 3)
        # Fall back to a transparent voltage-tier nominal when the bus is
        # islanded in the rendered subset (rare; happens for sub-HV-only
        # buses that survive the bus filter only because their tier is HV
        # but no >= 220 kV edge incidents). Keeps the SPA tooltip honest.
        if connected > 0.0:
            record["nearest_substation_capacity_mva"] = round(connected, 1)
        else:
            nominal = 4.0 if bus.voltage_kv >= EHV_THRESHOLD_KV else 2.0
            record["nearest_substation_capacity_mva"] = round(bus.voltage_kv * nominal, 1)
        updated += 1

    payload["records"] = records
    site_features_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return updated


# ----- Orchestration ------------------------------------------------------


def run_pypsa_ingestion(
    raw_dir: Path = RAW_DIR_DEFAULT,
    database: Path = DB_DEFAULT,
    geojson_out: Path = GEOJSON_DEFAULT,
    site_features: Path | None = SITE_FEATURES_DEFAULT,
    metadata_database: Path = METADATA_DB_DEFAULT,
    countries: Sequence[str] = DEFAULT_COUNTRIES,
    generated_at: str | None = None,
) -> IngestionResult:
    buses_path = raw_dir / "buses.csv"
    lines_path = raw_dir / "lines.csv"
    links_path = raw_dir / "links.csv"
    if not buses_path.exists() or not lines_path.exists():
        raise FileNotFoundError(
            f"PyPSA-Eur CSVs missing under {raw_dir}. "
            "Drop buses.csv and lines.csv (and optionally links.csv) there first."
        )

    buses = read_buses(buses_path)
    edges = [*read_lines(lines_path), *read_links(links_path)]

    write_database(database, buses, edges, raw_files=(buses_path, lines_path, links_path))

    payload = _build_geojson_payload(buses, edges)
    geojson_sha = write_geojson(geojson_out, payload)
    rendered_bus_count = int(payload["metadata"]["bus_count"])
    rendered_edge_count = int(payload["metadata"]["line_count"])

    overlay_updated = 0
    if site_features is not None:
        overlay_updated = overlay_nearest_substation(site_features, buses, edges)

    if generated_at is None:
        # Use a fixed epoch so artifact metadata stays deterministic across
        # repeat runs. The mtime on disk reflects the actual run; the
        # source_artifacts row is for content addressing, not wall-clock.
        generated_at = "1970-01-01T00:00:00+00:00"

    summary = ArtifactSummary(
        name=ARTIFACT_NAME,
        source=SOURCE_NAME,
        status="processed",
        source_status="processed",
        path=display_path(geojson_out, ROOT_DIR),
        checksum_sha256=geojson_sha,
        artifact_version=ARTIFACT_VERSION,
        record_count=rendered_bus_count + rendered_edge_count,
        fallback=None,
        notes=(
            f"PyPSA-Eur HV grid: {rendered_bus_count} buses, "
            f"{rendered_edge_count} lines >= {MIN_VOLTAGE_KV:.0f} kV; "
            f"overlay updated {overlay_updated} site records."
        ),
    )
    upsert_source_artifacts(
        metadata_database=metadata_database,
        countries=countries,
        generated_at=generated_at,
        artifacts=[summary],
    )

    return IngestionResult(
        raw_dir=raw_dir,
        database=database,
        geojson=geojson_out,
        site_features=site_features,
        bus_count=len(buses),
        line_count=sum(1 for e in edges if not e.is_hvdc),
        link_count=sum(1 for e in edges if e.is_hvdc),
        rendered_bus_count=rendered_bus_count,
        rendered_edge_count=rendered_edge_count,
        overlay_updated=overlay_updated,
    )


@app.callback(invoke_without_command=True)
def main(
    raw_dir: Annotated[
        Path,
        typer.Option("--raw-dir", help="Directory holding buses.csv, lines.csv, links.csv."),
    ] = RAW_DIR_DEFAULT,
    database: Annotated[
        Path,
        typer.Option("--database", help="SQLite database for the parsed grid."),
    ] = DB_DEFAULT,
    geojson_out: Annotated[
        Path,
        typer.Option("--geojson-out", help="Static GeoJSON consumed by the SPA."),
    ] = GEOJSON_DEFAULT,
    site_features: Annotated[
        Path,
        typer.Option(
            "--site-features",
            help="site_features_subset.json to enrich with nearest-substation fields.",
        ),
    ] = SITE_FEATURES_DEFAULT,
    metadata_database: Annotated[
        Path,
        typer.Option(
            "--metadata-database",
            help="SQLite database where source_artifacts rows are upserted.",
        ),
    ] = METADATA_DB_DEFAULT,
    skip_overlay: Annotated[
        bool,
        typer.Option(
            "--skip-overlay",
            help="Build the GeoJSON only; do not patch site_features_subset.json.",
        ),
    ] = False,
) -> None:
    """Ingest PyPSA-Eur CSVs and emit the grid GeoJSON + nearest-substation overlay."""

    result = run_pypsa_ingestion(
        raw_dir=raw_dir,
        database=database,
        geojson_out=geojson_out,
        site_features=None if skip_overlay else site_features,
        metadata_database=metadata_database,
    )
    typer.echo(
        f"Wrote {result.database} ({result.rendered_bus_count} buses, "
        f"{result.rendered_edge_count} lines >= {MIN_VOLTAGE_KV:.0f} kV)"
    )
    typer.echo(f"Wrote {result.geojson}")
    if result.site_features is not None:
        typer.echo(
            f"Patched {result.site_features} with nearest-substation fields "
            f"({result.overlay_updated} records)"
        )


if __name__ == "__main__":
    app()
