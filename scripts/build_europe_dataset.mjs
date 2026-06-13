// Generate the Europe-wide site dataset from curated metros and real
// country-level reference values.
//
// This is a one-off, deterministic build tool. It is the single source of the
// `SiteFeature` collection consumed by both the FastAPI backend
// (`backend/engine/data/europe_sites.json`) and the static SPA
// (`frontend/public/data/sites.json`).
//
// Why Node and not Python: H3 indexing is needed to place each cell, and the
// repo already ships `h3-js` transitively through deck.gl. Generating here
// avoids adding a Python `h3` dependency that the runtime never needs. The
// output is committed JSON, so nothing in this script runs at request time or
// during the Vercel build.
//
// Run:  node scripts/build_europe_dataset.mjs
//
// Values are grounded in public 2023-2024 reference figures (grid carbon
// intensity, wholesale price bands, latitude-driven solar yield, onshore wind
// capacity factors, and great-circle distance to real internet exchanges).
// They are reference estimates, not a live feed; see ASSUMPTIONS.md.

import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { writeFileSync } from "node:fs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");

// h3-js lives in the frontend workspace (deck.gl dependency); resolve it there.
const require = createRequire(resolve(ROOT, "frontend/package.json"));
const h3 = require("h3-js");

const H3_RESOLUTION = 5;

// --- Country reference table -------------------------------------------------
// carbon: annual grid carbon intensity (gCO2/kWh, ~2023, Ember/EEA-grounded).
// price:  representative day-ahead wholesale band (EUR/MWh, ~2023-2024).
// wind:   representative onshore wind capacity factor for the country.
const COUNTRIES = {
  SE: { name: "Sweden", carbon: 25, price: 50, wind: 0.34 },
  NO: { name: "Norway", carbon: 30, price: 52, wind: 0.33 },
  FI: { name: "Finland", carbon: 80, price: 56, wind: 0.32 },
  DK: { name: "Denmark", carbon: 180, price: 88, wind: 0.42 },
  IS: { name: "Iceland", carbon: 28, price: 43, wind: 0.4 },
  IE: { name: "Ireland", carbon: 350, price: 100, wind: 0.38 },
  GB: { name: "United Kingdom", carbon: 210, price: 96, wind: 0.36 },
  NL: { name: "Netherlands", carbon: 330, price: 90, wind: 0.34 },
  DE: { name: "Germany", carbon: 350, price: 95, wind: 0.27 },
  BE: { name: "Belgium", carbon: 140, price: 92, wind: 0.28 },
  FR: { name: "France", carbon: 56, price: 97, wind: 0.27 },
  CH: { name: "Switzerland", carbon: 45, price: 100, wind: 0.2 },
  AT: { name: "Austria", carbon: 110, price: 100, wind: 0.24 },
  ES: { name: "Spain", carbon: 150, price: 84, wind: 0.27 },
  PT: { name: "Portugal", carbon: 150, price: 84, wind: 0.28 },
  IT: { name: "Italy", carbon: 290, price: 125, wind: 0.22 },
  PL: { name: "Poland", carbon: 620, price: 92, wind: 0.3 },
  CZ: { name: "Czechia", carbon: 410, price: 100, wind: 0.23 },
  SK: { name: "Slovakia", carbon: 120, price: 100, wind: 0.22 },
  HU: { name: "Hungary", carbon: 200, price: 105, wind: 0.22 },
  RO: { name: "Romania", carbon: 260, price: 100, wind: 0.27 },
  BG: { name: "Bulgaria", carbon: 450, price: 110, wind: 0.26 },
  GR: { name: "Greece", carbon: 370, price: 130, wind: 0.25 },
  HR: { name: "Croatia", carbon: 220, price: 110, wind: 0.24 },
  SI: { name: "Slovenia", carbon: 240, price: 105, wind: 0.22 },
  RS: { name: "Serbia", carbon: 550, price: 105, wind: 0.24 },
  EE: { name: "Estonia", carbon: 450, price: 95, wind: 0.33 },
  LV: { name: "Latvia", carbon: 110, price: 95, wind: 0.31 },
  LT: { name: "Lithuania", carbon: 150, price: 95, wind: 0.32 },
  LU: { name: "Luxembourg", carbon: 110, price: 95, wind: 0.24 },
};

// Real internet-exchange locations; connectivity is great-circle to the nearest.
const IXPS = [
  [50.11, 8.68], // DE-CIX Frankfurt
  [52.37, 4.9], // AMS-IX Amsterdam
  [51.51, -0.13], // LINX London
  [48.86, 2.35], // France-IX Paris
  [45.46, 9.19], // MIX Milan
  [40.42, -3.7], // ESpanix Madrid
  [59.33, 18.06], // Netnod Stockholm
  [48.21, 16.37], // VIX Vienna
  [52.23, 21.01], // PLIX Warsaw
  [53.35, -6.26], // INEX Dublin
  [55.68, 12.57], // Netnod Copenhagen
  [47.38, 8.54], // SwissIX Zurich
  [50.85, 4.35], // BNIX Brussels
  [38.72, -9.14], // GigaPIX Lisbon
  [37.98, 23.73], // GR-IX Athens
  [44.43, 26.1], // InterLAN Bucharest
  [42.7, 23.32], // Sofia
  [50.08, 14.44], // NIX.CZ Prague
  [47.5, 19.04], // BIX Budapest
  [60.17, 24.94], // FICIX Helsinki
  [59.91, 10.75], // NIX Oslo
  [59.44, 24.75], // TLLIX Tallinn
  [56.95, 24.11], // Riga
  [43.3, 5.37], // France-IX Marseille
];

// tier drives demand pressure: hubs are dense and constrained, emerging metros
// have spare grid headroom and buildable land.
// [name, country, lat, lng, tier]
const METROS = [
  // Sweden
  ["Lulea / Boden", "SE", 65.5848, 22.1547, "emerging"],
  ["Sundsvall", "SE", 62.3908, 17.3069, "emerging"],
  ["Stockholm North", "SE", 59.437, 18.045, "hub"],
  ["Umea", "SE", 63.8258, 20.263, "emerging"],
  ["Gothenburg", "SE", 57.7089, 11.9746, "major"],
  ["Malmo", "SE", 55.604, 13.0038, "major"],
  // Norway
  ["Oslo", "NO", 59.9139, 10.7522, "major"],
  ["Bergen", "NO", 60.3913, 5.3221, "emerging"],
  ["Trondheim", "NO", 63.4305, 10.3951, "emerging"],
  ["Stavanger", "NO", 58.969, 5.7331, "emerging"],
  // Finland
  ["Helsinki", "FI", 60.1699, 24.9384, "major"],
  ["Tampere", "FI", 61.4978, 23.761, "emerging"],
  ["Oulu", "FI", 65.0121, 25.4651, "emerging"],
  // Denmark
  ["Copenhagen", "DK", 55.6761, 12.5683, "major"],
  ["Aarhus", "DK", 56.1629, 10.2039, "emerging"],
  ["Esbjerg", "DK", 55.4765, 8.4594, "emerging"],
  // Iceland
  ["Reykjavik", "IS", 64.1466, -21.9426, "emerging"],
  // Ireland
  ["Dublin West", "IE", 53.3498, -6.2603, "hub"],
  ["Galway East", "IE", 53.2707, -9.0568, "emerging"],
  ["Cork North", "IE", 51.8985, -8.4756, "major"],
  // United Kingdom
  ["London Slough", "GB", 51.5105, -0.5954, "hub"],
  ["Manchester", "GB", 53.4808, -2.2426, "major"],
  ["Newport Wales", "GB", 51.5842, -2.9977, "major"],
  ["Edinburgh", "GB", 55.9533, -3.1883, "emerging"],
  ["Leeds", "GB", 53.8008, -1.5491, "emerging"],
  // Netherlands
  ["Amsterdam", "NL", 52.3676, 4.9041, "hub"],
  ["Rotterdam", "NL", 51.9244, 4.4777, "major"],
  ["Eindhoven", "NL", 51.4416, 5.4697, "emerging"],
  ["Groningen", "NL", 53.2194, 6.5665, "emerging"],
  // Germany
  ["Frankfurt West", "DE", 50.1109, 8.6821, "hub"],
  ["Hamburg South", "DE", 53.5511, 9.9937, "major"],
  ["Munich North", "DE", 48.1351, 11.582, "major"],
  ["Berlin", "DE", 52.52, 13.405, "major"],
  ["Dusseldorf", "DE", 51.2277, 6.7735, "major"],
  ["Stuttgart", "DE", 48.7758, 9.1829, "major"],
  // Belgium
  ["Brussels", "BE", 50.8503, 4.3517, "major"],
  ["Antwerp", "BE", 51.2194, 4.4025, "major"],
  ["Mons", "BE", 50.4542, 3.9523, "emerging"],
  // France
  ["Paris", "FR", 48.8566, 2.3522, "hub"],
  ["Marseille", "FR", 43.2965, 5.3698, "major"],
  ["Lyon", "FR", 45.764, 4.8357, "major"],
  ["Lille", "FR", 50.6292, 3.0573, "major"],
  ["Bordeaux", "FR", 44.8378, -0.5792, "emerging"],
  ["Strasbourg", "FR", 48.5734, 7.7521, "emerging"],
  // Switzerland
  ["Zurich", "CH", 47.3769, 8.5417, "major"],
  ["Geneva", "CH", 46.2044, 6.1432, "major"],
  // Austria
  ["Vienna", "AT", 48.2082, 16.3738, "major"],
  ["Graz", "AT", 47.0707, 15.4395, "emerging"],
  // Spain
  ["Madrid", "ES", 40.4168, -3.7038, "major"],
  ["Barcelona", "ES", 41.3874, 2.1686, "major"],
  ["Bilbao", "ES", 43.263, -2.935, "emerging"],
  ["Seville", "ES", 37.3891, -5.9845, "emerging"],
  ["Valencia", "ES", 39.4699, -0.3763, "emerging"],
  // Portugal
  ["Lisbon", "PT", 38.7223, -9.1393, "major"],
  ["Porto", "PT", 41.1579, -8.6291, "emerging"],
  // Italy
  ["Milan", "IT", 45.4642, 9.19, "hub"],
  ["Rome", "IT", 41.9028, 12.4964, "major"],
  ["Turin", "IT", 45.0703, 7.6869, "major"],
  ["Naples", "IT", 40.8518, 14.2681, "emerging"],
  ["Palermo", "IT", 38.1157, 13.3615, "emerging"],
  // Poland
  ["Warsaw", "PL", 52.2297, 21.0122, "major"],
  ["Krakow", "PL", 50.0647, 19.945, "emerging"],
  ["Gdansk", "PL", 54.352, 18.6466, "emerging"],
  ["Katowice", "PL", 50.2649, 19.0238, "major"],
  ["Poznan", "PL", 52.4064, 16.9252, "emerging"],
  // Czechia
  ["Prague", "CZ", 50.0755, 14.4378, "major"],
  ["Brno", "CZ", 49.1951, 16.6068, "emerging"],
  // Slovakia
  ["Bratislava", "SK", 48.1486, 17.1077, "emerging"],
  // Hungary
  ["Budapest", "HU", 47.4979, 19.0402, "major"],
  // Romania
  ["Bucharest", "RO", 44.4268, 26.1025, "major"],
  ["Cluj-Napoca", "RO", 46.7712, 23.6236, "emerging"],
  // Bulgaria
  ["Sofia", "BG", 42.6977, 23.3219, "emerging"],
  // Greece
  ["Athens", "GR", 37.9838, 23.7275, "major"],
  ["Thessaloniki", "GR", 40.6401, 22.9444, "emerging"],
  // Croatia
  ["Zagreb", "HR", 45.815, 15.9819, "emerging"],
  // Slovenia
  ["Ljubljana", "SI", 46.0569, 14.5058, "emerging"],
  // Serbia
  ["Belgrade", "RS", 44.7866, 20.4489, "emerging"],
  // Baltics
  ["Tallinn", "EE", 59.437, 24.7536, "emerging"],
  ["Riga", "LV", 56.9496, 24.1052, "emerging"],
  ["Vilnius", "LT", 54.6872, 25.2797, "emerging"],
  // Luxembourg
  ["Luxembourg City", "LU", 49.6116, 6.1319, "major"],
];

// Per-tier center values; a deterministic per-metro jitter spreads cells within
// each band so the map and ranking are not visibly stepped.
const TIER = {
  hub: { headroom: 320, congestion: 0.82, fiber: 2.5, substation: 4.0, dcSim: 0.84 },
  major: { headroom: 420, congestion: 0.52, fiber: 7.0, substation: 7.5, dcSim: 0.7 },
  emerging: { headroom: 560, congestion: 0.28, fiber: 14.0, substation: 11.5, dcSim: 0.52 },
};

const clamp = (value, low, high) => Math.min(Math.max(value, low), high);
const round = (value, digits) => {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
};

// Deterministic [0,1) hash of a string (FNV-1a), used for stable jitter.
function unitHash(text) {
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) % 100000) / 100000;
}

function haversineKm(aLat, aLng, bLat, bLng) {
  const toRad = (deg) => (deg * Math.PI) / 180;
  const earthKm = 6371;
  const dLat = toRad(bLat - aLat);
  const dLng = toRad(bLng - aLng);
  const lat1 = toRad(aLat);
  const lat2 = toRad(bLat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return earthKm * 2 * Math.asin(Math.sqrt(h));
}

function nearestIxpKm(lat, lng) {
  let best = Infinity;
  for (const [ixpLat, ixpLng] of IXPS) {
    best = Math.min(best, haversineKm(lat, lng, ixpLat, ixpLng));
  }
  return best;
}

function buildSite([name, country, lat, lng, tier]) {
  const ref = COUNTRIES[country];
  if (!ref) throw new Error(`Unknown country code: ${country}`);
  const band = TIER[tier];
  // Two independent jitter streams so correlated fields do not move in lockstep.
  const jA = unitHash(`${name}:${country}:a`);
  const jB = unitHash(`${name}:${country}:b`);

  const carbon = ref.carbon;
  const price = round(ref.price * (0.96 + jA * 0.12) + (tier === "hub" ? 6 : 0), 1);
  const priceVolatility = round(price * (0.28 + carbon / 2600), 1);

  const solarCf = round(clamp(0.205 - (lat - 37) * 0.0034, 0.085, 0.205), 3);
  const windCf = round(clamp(ref.wind + Math.max(0, lat - 50) * 0.0028 + (jB - 0.5) * 0.03, 0.15, 0.48), 3);

  const congestion = round(clamp(band.congestion + (jA - 0.5) * 0.16, 0.12, 0.95), 2);
  const headroom = round(clamp(band.headroom * (0.85 + jB * 0.3) - congestion * 90, 110, 680), 0);

  const distIxp = round(nearestIxpKm(lat, lng), 1);
  const distFiber = round(clamp(band.fiber * (0.7 + jA * 0.6) + distIxp * 0.04, 0.5, 30), 1);
  const distSubstation = round(clamp(band.substation * (0.7 + jB * 0.6), 1.5, 18), 1);
  const latencyMs = round(clamp(0.6 + distIxp / 90 + (tier === "hub" ? 0.4 : 1.2) * jA, 0.6, 18), 1);

  const waterDist = round(clamp(1.2 + jB * 5.5, 0.8, 7.5), 1);
  const coolingProxy = round(clamp(0.68 - (lat - 37) * 0.016, 0.12, 0.68), 2);
  const buildable = round(clamp(0.86 - congestion * 0.55 + (jA - 0.5) * 0.08, 0.3, 0.85), 2);
  const dcSimilarity = round(clamp(band.dcSim + (jB - 0.5) * 0.12, 0.38, 0.92), 2);

  // Transparent composite viability proxy (the LightGBM fallback): reward low
  // carbon, low congestion, strong connectivity, buildable land, and similarity
  // to known data-center sites. Bounded to [0, 1].
  const carbonScore = clamp(1 - carbon / 650, 0, 1);
  const congestionScore = 1 - congestion;
  const connectivityScore = clamp(1 - distIxp / 600, 0, 1);
  const viability = round(
    clamp(
      0.3 * carbonScore +
        0.2 * congestionScore +
        0.2 * connectivityScore +
        0.15 * buildable +
        0.15 * dcSimilarity,
      0.05,
      0.97,
    ),
    2,
  );

  // SHAP-style top contributors: the three strongest drivers of the proxy.
  const drivers = [
    ["carbon_intensity_g_kwh", round(0.3 * (carbonScore - 0.5), 3)],
    ["congestion_index", round(0.2 * (congestionScore - 0.5), 3)],
    ["dist_ixp_km", round(0.2 * (connectivityScore - 0.5), 3)],
    ["buildable_fraction", round(0.15 * (buildable - 0.5), 3)],
    ["dc_similarity", round(0.15 * (dcSimilarity - 0.5), 3)],
  ]
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 3);

  return {
    cell_id: h3.latLngToCell(lat, lng, H3_RESOLUTION),
    country_code: country,
    region_name: name,
    latitude: lat,
    longitude: lng,
    resolution: H3_RESOLUTION,
    mean_price_eur_mwh: price,
    price_volatility: priceVolatility,
    carbon_intensity_g_kwh: carbon,
    congestion_index: congestion,
    headroom_mw: headroom,
    dist_hv_substation_km: distSubstation,
    dist_fiber_km: distFiber,
    dist_ixp_km: distIxp,
    latency_proxy_ms: latencyMs,
    solar_cf: solarCf,
    wind_cf: windCf,
    water_dist_km: waterDist,
    cooling_degree_proxy: coolingProxy,
    buildable_fraction: buildable,
    dc_similarity: dcSimilarity,
    lightgbm_score: viability,
    shap_values: Object.fromEntries(drivers),
    exclusion_flag: false,
  };
}

function main() {
  const seen = new Map();
  const sites = [];
  for (const metro of METROS) {
    const site = buildSite(metro);
    if (seen.has(site.cell_id)) {
      throw new Error(
        `H3 collision at res ${H3_RESOLUTION}: "${site.region_name}" and ` +
          `"${seen.get(site.cell_id)}" share ${site.cell_id}. Nudge a coordinate.`,
      );
    }
    seen.set(site.cell_id, site.region_name);
    sites.push(site);
  }
  // Stable order: country, then region name. Keeps diffs and layers reproducible.
  sites.sort(
    (a, b) =>
      a.country_code.localeCompare(b.country_code) ||
      a.region_name.localeCompare(b.region_name),
  );

  const json = `${JSON.stringify(sites, null, 2)}\n`;
  const backendPath = resolve(ROOT, "backend/engine/data/europe_sites.json");
  const frontendPath = resolve(ROOT, "frontend/public/data/sites.json");
  writeFileSync(backendPath, json);
  writeFileSync(frontendPath, json);

  const countries = new Set(sites.map((s) => s.country_code));
  console.log(`Wrote ${sites.length} sites across ${countries.size} countries.`);
  console.log(`- ${backendPath}`);
  console.log(`- ${frontendPath}`);
}

main();
