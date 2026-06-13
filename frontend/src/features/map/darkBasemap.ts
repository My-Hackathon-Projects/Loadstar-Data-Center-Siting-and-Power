import type { StyleSpecification } from "maplibre-gl";

import { COLOR } from "../../styles/tokens";

/**
 * Self-hosted, simplified Natural Earth 110m country geometry. Bundled under
 * public/ so the basemap renders fully offline — no tile server, no API key,
 * and no network fetch that could block an intro phase transition.
 */
export const COUNTRIES_URL = "/geo/countries-110m.geojson";

/**
 * The dark cinematic basemap shared by the intro globe and the dashboard map.
 * Ocean is the deep void; land is a slightly lifted panel surface with thin,
 * low-opacity borders. Pass `globe` to switch on MapLibre v5 globe projection
 * for the arrival sequence; the dashboard keeps mercator so the Deck.GL H3
 * overlay stays aligned.
 */
export function darkBasemapStyle(options?: { globe?: boolean }): StyleSpecification {
  return {
    version: 8,
    projection: { type: options?.globe ? "globe" : "mercator" },
    sources: {
      countries: { type: "geojson", data: COUNTRIES_URL },
    },
    layers: [
      {
        id: "void",
        type: "background",
        paint: { "background-color": COLOR.bgVoid },
      },
      {
        id: "country-fill",
        type: "fill",
        source: "countries",
        paint: { "fill-color": COLOR.bgPanelRaised, "fill-opacity": 0.9 },
      },
      {
        id: "country-line",
        type: "line",
        source: "countries",
        paint: { "line-color": COLOR.borderSubtle, "line-width": 0.6 },
      },
    ],
  };
}
