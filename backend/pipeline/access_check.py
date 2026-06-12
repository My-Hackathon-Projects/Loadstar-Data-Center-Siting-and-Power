"""Task-zero external-source access checks.

Probes Zenodo, Ember, ITU BBmaps, and Earth Engine and writes a decision
record (`public/docs/access_decisions.md`) describing availability and the
downstream fallback implication for each blocked source. Never echoes secrets.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

ZENODO_RECORD_URL = "https://zenodo.org/api/records/18619025"
EMBER_ROOT_URL = "https://api.ember-climate.org"
ITU_BBMAPS_URL = "https://bbmaps.itu.int"
app = typer.Typer(add_completion=False, help="Run task-zero external source access checks.")


@dataclass
class SourceDecision:
    source: str
    status: str
    check: str
    evidence: str
    downstream_implication: str
    fallback: str | None = None


def _fetch_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.reason}
    except Exception as exc:  # noqa: BLE001 - surfaced as decision-record evidence.
        return 0, {"error": str(exc)}


def _curl_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> tuple[int, Any]:
    command = ["curl", "-sS", "-L", "-w", "\n%{http_code}", "--max-time", str(timeout)]
    for key, value in (headers or {}).items():
        command.extend(["-H", f"{key}: {value}"])
    command.append(url)
    process = subprocess.run(command, text=True, capture_output=True)
    if process.returncode != 0:
        return 0, {"error": process.stderr.strip() or "curl failed"}
    body, _, status_text = process.stdout.rpartition("\n")
    try:
        status = int(status_text)
    except ValueError:
        status = 0
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = {"body_preview": body[:500]}
    return status, payload


def _fetch_head(url: str, timeout: int = 20) -> tuple[int, str]:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final_url = response.geturl()
            return response.status, final_url
    except urllib.error.HTTPError as exc:
        return exc.code, exc.reason
    except Exception as exc:  # noqa: BLE001 - surfaced as decision-record evidence.
        return 0, str(exc)


def _curl_head(url: str, timeout: int = 20) -> tuple[int, str]:
    process = subprocess.run(
        [
            "curl",
            "-sS",
            "-L",
            "-I",
            "-w",
            "\n%{http_code} %{url_effective}",
            "--max-time",
            str(timeout),
            url,
        ],
        text=True,
        capture_output=True,
    )
    if process.returncode != 0:
        return 0, process.stderr.strip() or "curl failed"
    marker = process.stdout.strip().splitlines()[-1]
    status_text, _, final_url = marker.partition(" ")
    try:
        return int(status_text), final_url
    except ValueError:
        return 0, marker


def check_zenodo() -> SourceDecision:
    status, payload = _curl_json(ZENODO_RECORD_URL)
    files = payload.get("files", []) if isinstance(payload, dict) else []
    required = {"buses.csv", "lines.csv"}
    present = {item.get("key") for item in files}
    if status == 200 and required.issubset(present):
        return SourceDecision(
            source="Zenodo PyPSA-Eur record 18619025",
            status="ok",
            check="Fetched record metadata and confirmed buses.csv and lines.csv artifacts.",
            evidence=f"HTTP 200; files={', '.join(sorted(present))}",
            downstream_implication=(
                "Issue 6 can download the PyPSA-Eur OSM network and produce the OPF artifact."
            ),
        )
    return SourceDecision(
        source="Zenodo PyPSA-Eur record 18619025",
        status="fallback",
        check="Fetched record metadata and checked for required artifacts.",
        evidence=f"HTTP {status}; payload={payload}",
        downstream_implication=(
            "Issue 6 cannot produce OPF-derived headroom/congestion until access is restored."
        ),
        fallback="Use fixture headroom and congestion fields in the walking skeleton.",
    )


def check_itu_bbmaps() -> SourceDecision:
    test_url = os.getenv("ITU_BBMAPS_TEST_URL", ITU_BBMAPS_URL)
    status, final_url = _curl_head(test_url)
    if status == 200 and os.getenv("ITU_BBMAPS_TEST_URL"):
        return SourceDecision(
            source="ITU BBmaps",
            status="ok",
            check="Fetched configured BBmaps feature/WMS test URL.",
            evidence=f"HTTP 200; final_url={final_url}",
            downstream_implication=(
                "Issue 6 can ingest ITU fiber features and issue 8 can expose `dist_fiber_km`."
            ),
        )
    if status in {200, 301, 302}:
        return SourceDecision(
            source="ITU BBmaps",
            status="fallback",
            check=(
                "Confirmed public ITU transmission map page is reachable, but no feature "
                "extraction URL was configured."
            ),
            evidence=f"HTTP {status}; final_url={final_url}",
            downstream_implication=(
                "Issue 6 should ingest IXP distances instead, and issue 8 should label "
                "connectivity as an IXP/connectivity proxy until BBmaps extraction is "
                "available."
            ),
            fallback=(
                "Use OSM/PeeringDB IXP distance proxy for `dist_ixp_km`; keep "
                "`dist_fiber_km` flagged as provisional."
            ),
        )
    return SourceDecision(
        source="ITU BBmaps",
        status="blocked",
        check="Attempted to reach BBmaps endpoint.",
        evidence=f"HTTP {status}; result={final_url}",
        downstream_implication=(
            "Issue 6 must use IXP distance fallback and document missing fiber extraction."
        ),
        fallback="Use IXP distance proxy.",
    )


def check_ember() -> SourceDecision:
    hourly_url = os.getenv("EMBER_HOURLY_PRICE_URL")
    api_key = os.getenv("EMBER_API_KEY")
    if not hourly_url:
        status, _ = _curl_head(EMBER_ROOT_URL)
        return SourceDecision(
            source="Ember hourly electricity prices",
            status="blocked",
            check="No EMBER_HOURLY_PRICE_URL was configured for an actual hourly price pull.",
            evidence=(
                f"Root endpoint probe returned HTTP {status}; hourly data endpoint not verified."
            ),
            downstream_implication=(
                "Issue 6 must not assume Ember hourly price access. Use a verified "
                "endpoint or fallback before replacing fixture prices."
            ),
            fallback="Use checked fixture prices or ENTSO-E-backed prices with provisional labels.",
        )

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    status, payload = _curl_json(hourly_url, headers=headers)
    if status == 200:
        return SourceDecision(
            source="Ember hourly electricity prices",
            status="ok",
            check="Fetched configured hourly price URL.",
            evidence="HTTP 200; JSON response received.",
            downstream_implication=(
                "Issue 6 can ingest Ember hourly prices for the configured zones."
            ),
        )
    return SourceDecision(
        source="Ember hourly electricity prices",
        status="blocked",
        check="Attempted configured hourly price URL.",
        evidence=f"HTTP {status}; payload={payload}",
        downstream_implication=(
            "Issue 6 must use fallback pricing until the Ember endpoint/key is corrected."
        ),
        fallback="Use ENTSO-E-backed or fixture hourly prices with provisional labels.",
    )


def check_earth_engine() -> SourceDecision:
    project = os.getenv("EARTHENGINE_PROJECT")
    if not project:
        return SourceDecision(
            source="Google Earth Engine / AlphaEarth",
            status="blocked",
            check=(
                "EARTHENGINE_PROJECT is not configured, so an AlphaEarth embedding sample "
                "cannot run."
            ),
            evidence="Missing EARTHENGINE_PROJECT.",
            downstream_implication=(
                "Issues 9 and 10 must proceed without AlphaEarth-derived features until "
                "approval/access is available."
            ),
            fallback=(
                "Use non-embedding land features and transparent scoring; omit "
                "`buildable_fraction` model output if needed."
            ),
        )
    try:
        import ee  # type: ignore

        ee.Initialize(project=project)
        image = (
            ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL")
            .filterDate("2024-01-01", "2025-01-01")
            .first()
        )
        point = ee.Geometry.Point([22.1547, 65.5848])
        sample = image.sample(point, scale=10, numPixels=1).first().getInfo()
        if sample:
            return SourceDecision(
                source="Google Earth Engine / AlphaEarth",
                status="ok",
                check=(
                    "Initialized Earth Engine and sampled one AlphaEarth embedding pixel "
                    "near Lulea."
                ),
                evidence="Earth Engine sample returned one feature.",
                downstream_implication=(
                    "Issue 9 can train/export AlphaEarth-derived land suitability features."
                ),
            )
        raise RuntimeError("Earth Engine sample returned no feature.")
    except Exception as exc:  # noqa: BLE001 - surfaced as decision-record evidence.
        return SourceDecision(
            source="Google Earth Engine / AlphaEarth",
            status="blocked",
            check="Attempted Earth Engine AlphaEarth embedding sample.",
            evidence=str(exc),
            downstream_implication=(
                "Issues 9 and 10 lose AlphaEarth features until project approval, package "
                "setup, or dataset access is fixed."
            ),
            fallback="Use non-embedding land features and transparent scoring.",
        )


def run_checks() -> list[SourceDecision]:
    return [check_earth_engine(), check_ember(), check_itu_bbmaps(), check_zenodo()]


def render_markdown(decisions: list[SourceDecision]) -> str:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    lines = [
        "# External Source Access Decisions",
        "",
        f"Generated at: `{generated_at}`",
        "",
        (
            "This file is a decision record for issue 2. It records not only source "
            "status, but also what each status implies downstream."
        ),
        "",
        "| Source | Status | Check | Evidence | Downstream implication | Fallback |",
        "|---|---|---|---|---|---|",
    ]
    row_template = (
        "| {source} | `{status}` | {check} | {evidence} | {downstream_implication} | {fallback} |"
    )
    for decision in decisions:
        lines.append(
            row_template.format(
                source=decision.source,
                status=decision.status,
                check=decision.check.replace("|", "\\|"),
                evidence=decision.evidence.replace("|", "\\|"),
                downstream_implication=decision.downstream_implication.replace("|", "\\|"),
                fallback=(decision.fallback or "").replace("|", "\\|"),
            )
        )
    lines.append("")
    return "\n".join(lines)


@app.callback(invoke_without_command=True)
def main(
    write: Annotated[
        Path | None,
        typer.Option("--write", help="Write a Markdown decision record to this path."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print JSON instead of Markdown."),
    ] = False,
) -> None:
    """Run all configured source access checks."""

    decisions = run_checks()
    if write:
        write.parent.mkdir(parents=True, exist_ok=True)
        write.write_text(render_markdown(decisions), encoding="utf-8")

    if json_output:
        print(json.dumps([asdict(decision) for decision in decisions], indent=2))
    else:
        print(render_markdown(decisions))


if __name__ == "__main__":
    app()
