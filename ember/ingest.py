"""Standalone Ember electricity-price ingestion.

Downloads Ember's free European wholesale day-ahead price dataset (the hourly
zip — no API key) and reduces it to a per-country profile stored in a local
SQLite database. The expensive ~40 MB zip parse is a one-time step; everything
downstream reads the DB.

Self-contained: standard library only, no project imports. Run it directly:

    python ember/ingest.py                 # default scope SE,DE,IE, year 2025
    python ember/ingest.py --countries SE,DE,IE,NO,FR --year 2025

Why a CSV download and not the API: Ember's REST API (api.ember-energy.org)
serves only carbon/generation data — hourly *prices* exist solely as this free
CSV/zip bundle. See ember/ember.md.

Per-country CSVs inside the zip have columns:
    Country, ISO3 Code, Datetime (UTC), Datetime (Local), Price (EUR/MWhe)
"""

from __future__ import annotations

import argparse
import csv
import io
import sqlite3
import statistics
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

# Live, key-free download (the legacy ember-climate.org/app/uploads links 404).
EMBER_HOURLY_ZIP_URL = (
    "https://storage.googleapis.com/emb-prod-bkt-publicdata/"
    "public-downloads/price/outputs/"
    "european_wholesale_electricity_price_data_hourly.zip"
)

DATASET_DIR = Path(__file__).resolve().parent / "dataset"
ZIP_PATH = DATASET_DIR / "european_wholesale_electricity_price_data_hourly.zip"
DB_PATH = DATASET_DIR / "ember_prices.db"

DEFAULT_COUNTRIES = ("SE", "DE", "IE")
DEFAULT_YEAR = 2025

# ISO-2 -> (per-country CSV name inside the zip, ISO3 code used to verify rows).
# Add a row here to support more countries.
ISO2_TO_EMBER: dict[str, tuple[str, str]] = {
    "SE": ("Sweden.csv", "SWE"),
    "DE": ("Germany.csv", "DEU"),
    "IE": ("Ireland.csv", "IRL"),
    "NO": ("Norway.csv", "NOR"),
    "FI": ("Finland.csv", "FIN"),
    "DK": ("Denmark.csv", "DNK"),
    "FR": ("France.csv", "FRA"),
    "NL": ("Netherlands.csv", "NLD"),
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ember_price_profile (
    zone_id TEXT NOT NULL,
    iso3_code TEXT NOT NULL,
    sample_year INTEGER NOT NULL,
    mean_price_eur_mwh REAL NOT NULL,
    price_volatility REAL NOT NULL,
    sample_hours INTEGER NOT NULL,
    PRIMARY KEY (zone_id, sample_year)
);
CREATE TABLE IF NOT EXISTS ember_price_hourly_shape (
    zone_id TEXT NOT NULL,
    sample_year INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    shape_multiplier REAL NOT NULL,
    hour_mean_price_eur_mwh REAL NOT NULL,
    PRIMARY KEY (zone_id, sample_year, hour)
);
CREATE TABLE IF NOT EXISTS ember_price_hourly (
    zone_id TEXT NOT NULL,
    sample_year INTEGER NOT NULL,
    datetime_utc TEXT NOT NULL,
    price_eur_mwh REAL NOT NULL,
    PRIMARY KEY (zone_id, datetime_utc)
);
"""


@dataclass(frozen=True)
class CountryProfile:
    zone_id: str
    iso3_code: str
    sample_year: int
    sample_hours: int
    mean_price_eur_mwh: float
    price_volatility: float
    hour_of_day_shape: list[float]  # 24 multipliers around 1.0
    hour_mean_price: list[float]  # 24 absolute EUR/MWh
    series: list[tuple[str, float]]  # (datetime_utc, price) full in-year series


def ensure_zip() -> Path:
    """Download the Ember zip into ember/dataset/ if not already present."""

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    if not ZIP_PATH.exists():
        print(f"Downloading Ember price zip (~40 MB) -> {ZIP_PATH} ...")
        urllib.request.urlretrieve(EMBER_HOURLY_ZIP_URL, ZIP_PATH)  # noqa: S310 - fixed https URL
    else:
        print(f"Using cached zip: {ZIP_PATH}")
    return ZIP_PATH


def build_profile(bundle: zipfile.ZipFile, code: str, year: int) -> CountryProfile:
    csv_name, iso3 = ISO2_TO_EMBER[code]
    if csv_name not in set(bundle.namelist()):
        raise ValueError(f"Ember zip is missing {csv_name} for {code}.")

    prices: list[float] = []
    series: list[tuple[str, float]] = []
    hourly_buckets: dict[int, list[float]] = {hour: [] for hour in range(24)}
    with bundle.open(csv_name) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"))
        for row in reader:
            if row.get("ISO3 Code") != iso3:
                continue
            timestamp = row.get("Datetime (UTC)", "")
            price_text = row.get("Price (EUR/MWhe)", "")
            if len(timestamp) < 13 or not price_text:
                continue
            if int(timestamp[0:4]) != year:
                continue
            try:
                price = float(price_text)
            except ValueError:
                continue
            prices.append(price)
            series.append((timestamp, price))
            hourly_buckets[int(timestamp[11:13])].append(price)
    if not prices:
        raise ValueError(f"No {year} price rows found in {csv_name} for {iso3}.")

    mean_price = statistics.fmean(prices)
    volatility = statistics.pstdev(prices)
    base = mean_price if mean_price > 0 else 1.0
    shape: list[float] = []
    hour_mean_price: list[float] = []
    for hour in range(24):
        bucket = hourly_buckets[hour]
        hour_mean = statistics.fmean(bucket) if bucket else mean_price
        shape.append(round(hour_mean / base, 4))
        hour_mean_price.append(round(hour_mean, 2))
    return CountryProfile(
        zone_id=code,
        iso3_code=iso3,
        sample_year=year,
        sample_hours=len(prices),
        mean_price_eur_mwh=round(mean_price, 2),
        price_volatility=round(volatility, 2),
        hour_of_day_shape=shape,
        hour_mean_price=hour_mean_price,
        series=series,
    )


def write_database(profiles: list[CountryProfile]) -> int:
    """Persist profiles to SQLite. Idempotent per (zone, year). Returns rows."""

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    hourly_rows = 0
    with sqlite3.connect(DB_PATH) as connection:
        connection.executescript(SCHEMA_SQL)
        for profile in profiles:
            zone, year = profile.zone_id, profile.sample_year
            connection.execute(
                "DELETE FROM ember_price_profile WHERE zone_id = ? AND sample_year = ?",
                (zone, year),
            )
            connection.execute(
                "DELETE FROM ember_price_hourly_shape WHERE zone_id = ? AND sample_year = ?",
                (zone, year),
            )
            connection.execute(
                "DELETE FROM ember_price_hourly WHERE zone_id = ? AND sample_year = ?",
                (zone, year),
            )
            connection.execute(
                """
                INSERT INTO ember_price_profile (
                    zone_id, iso3_code, sample_year, mean_price_eur_mwh,
                    price_volatility, sample_hours
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    zone,
                    profile.iso3_code,
                    year,
                    profile.mean_price_eur_mwh,
                    profile.price_volatility,
                    profile.sample_hours,
                ),
            )
            connection.executemany(
                """
                INSERT INTO ember_price_hourly_shape (
                    zone_id, sample_year, hour, shape_multiplier, hour_mean_price_eur_mwh
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        zone,
                        year,
                        hour,
                        profile.hour_of_day_shape[hour],
                        profile.hour_mean_price[hour],
                    )
                    for hour in range(24)
                ],
            )
            connection.executemany(
                """
                INSERT INTO ember_price_hourly (zone_id, sample_year, datetime_utc, price_eur_mwh)
                VALUES (?, ?, ?, ?)
                """,
                [(zone, year, timestamp, price) for timestamp, price in profile.series],
            )
            hourly_rows += len(profile.series)
        connection.commit()
    return hourly_rows


def parse_countries(raw: str) -> list[str]:
    codes: list[str] = []
    for token in raw.split(","):
        code = token.strip().upper()
        if not code:
            continue
        if code not in ISO2_TO_EMBER:
            supported = ", ".join(sorted(ISO2_TO_EMBER))
            raise SystemExit(f"Unsupported country {code!r}. Supported: {supported}.")
        if code not in codes:
            codes.append(code)
    if not codes:
        raise SystemExit("At least one country is required.")
    return codes


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Ember price SQLite database.")
    parser.add_argument(
        "--countries",
        default=",".join(DEFAULT_COUNTRIES),
        help="Comma-separated ISO-3166 alpha-2 codes (default: SE,DE,IE).",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_YEAR,
        help=f"Calendar year to summarize (default: {DEFAULT_YEAR}).",
    )
    args = parser.parse_args()
    countries = parse_countries(args.countries)

    zip_path = ensure_zip()
    with zipfile.ZipFile(zip_path) as bundle:
        profiles = [build_profile(bundle, code, args.year) for code in countries]
    hourly_rows = write_database(profiles)

    print(f"\nWrote {DB_PATH} ({hourly_rows} hourly rows, year {args.year})")
    print(f"{'zone':5} {'mean':>8} {'volatility':>11} {'hours':>7}")
    for profile in profiles:
        print(
            f"{profile.zone_id:5} {profile.mean_price_eur_mwh:8.2f} "
            f"{profile.price_volatility:11.2f} {profile.sample_hours:7d}"
        )


if __name__ == "__main__":
    main()
