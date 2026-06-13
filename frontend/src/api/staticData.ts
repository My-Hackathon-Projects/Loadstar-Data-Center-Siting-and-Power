/**
 * Static dataset access for the no-backend (deployed) path.
 *
 * The committed `public/data/sites.json` is the same Europe-wide `SiteFeature`
 * collection the backend serves. Loading it lets search, detail, and compare
 * run entirely in the browser when no API origin is reachable (the Vercel
 * static deployment). Locally, where the API is up, this is never hit.
 */

import type { SiteFeature } from "../types/api";
import { API_BASE_URL } from "../config/env";

let sitesPromise: Promise<SiteFeature[]> | null = null;

/** Fetch and cache the static site collection for the session. */
export function loadSites(): Promise<SiteFeature[]> {
  if (!sitesPromise) {
    sitesPromise = fetch(`${API_BASE_URL}/data/sites.json`, {
      headers: { Accept: "application/json" },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Static dataset unavailable: ${response.status}`);
        }
        return response.json() as Promise<SiteFeature[]>;
      })
      .catch((error: unknown) => {
        // Reset so a transient failure can be retried by the next caller.
        sitesPromise = null;
        throw error;
      });
  }
  return sitesPromise;
}
