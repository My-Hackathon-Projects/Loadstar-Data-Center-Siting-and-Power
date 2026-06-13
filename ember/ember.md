# Ember Electricity Prices

Self-contained tool that turns Ember's free European electricity-price dataset
into a local SQLite database. Replaces hardcoded fixture prices with real
hourly market data.

## The gotcha (read this first)

Ember has **two** data channels and they are easy to confuse:

- **REST API** (`api.ember-energy.org`) — serves carbon intensity, generation,
  demand, emissions. **Monthly/yearly only. No prices.** Needs a key.
- **CSV / zip download** — serves **wholesale day-ahead prices** (hourly).
  **No API key.** This is the only place hourly prices exist.

We lost time pointing the API at price data it doesn't have (got HTTP 404). The
working, key-free download is:

```
https://storage.googleapis.com/emb-prod-bkt-publicdata/public-downloads/price/outputs/european_wholesale_electricity_price_data_hourly.zip
```

(The older `ember-climate.org/app/uploads/...` links are dead/404.)

The zip is ~40 MB: `all_countries.csv` plus one CSV per country. Columns:
`Country, ISO3 Code, Datetime (UTC), Datetime (Local), Price (EUR/MWhe)`.
Hourly, 2015→present, 32 European countries. **Country-level only** (no
bidding zones like SE1–SE4).

## How to run

```bash
python ember/ingest.py                          # default: SE,DE,IE, year 2025
python ember/ingest.py --countries SE,DE,IE,NO,FR --year 2025
```

The script downloads the zip into `ember/dataset/` (skipped if already there),
parses it, and writes `ember/dataset/ember_prices.db`. Re-running is safe
(idempotent per country + year). Standard library only — no dependencies.

Supported countries: SE, DE, IE, NO, FI, DK, FR, NL. Add a row to
`ISO2_TO_EMBER` in `ingest.py` to support more.

## What it produces

`ember/dataset/ember_prices.db` — three tables:

| Table | Rows (SE,DE,IE) | Contents |
|---|---|---|
| `ember_price_profile` | 3 | per country-year: mean price, volatility, sample size |
| `ember_price_hourly_shape` | 72 | 24 hour-of-day rows per country: multiplier + absolute price |
| `ember_price_hourly` | 26,280 | the full 8,760-hour series per country |

The `hourly_shape` table is the useful one for the optimizer: multiply a
country's mean price by `shape_multiplier[hour]` to get a realistic 24-hour
price curve. The full `ember_price_hourly` series is there for full-year work.

### Real 2025 values (sanity check)

| Country | Mean €/MWh | Volatility | Cheapest hour | Priciest hour |
|---|---|---|---|---|
| SE | 42.6 | 38.2 | 01:00 | 17:00 |
| DE | 89.5 | 50.8 | 11:00 (solar glut) | 17:00 |
| IE | 114.4 | 54.3 | 03:00 | 18:00 |

DE's midday trough is the real solar duck-curve — the kind of pattern a
synthetic price curve can't reproduce.

## Example query

```sql
-- realistic 24h price curve for Germany in 2025
SELECT hour, hour_mean_price_eur_mwh
FROM ember_price_hourly_shape
WHERE zone_id = 'DE' AND sample_year = 2025
ORDER BY hour;
```

## Files

```
ember/
  ingest.py    standalone script (stdlib only)
  ember.md     this file
  dataset/     the downloaded zip + ember_prices.db  (gitignored, stays local)
```

## Notes

- `ember/dataset/` is gitignored — the 40 MB zip and the DB are not committed.
  Each person runs `ingest.py` once locally.
- Prices are country-level. For within-country / regional resolution the
  project blends these with PyPSA-Eur grid data.
- A valid Ember API key only unlocks carbon/generation, never prices — so the
  CSV download is the right and only source here.
