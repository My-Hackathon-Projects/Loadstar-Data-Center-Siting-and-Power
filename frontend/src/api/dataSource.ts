/**
 * Decides whether the REST API is reachable, once per session.
 *
 * Local development serves the FastAPI backend at the same origin (via the
 * Vite proxy), so the live engine handles everything. The deployed SPA on
 * Vercel is static with no API origin, so `/health` 404s and the read path
 * falls back to the in-browser engine over the committed dataset.
 *
 * Probing once (and caching the promise) avoids a failing request on every
 * keystroke-driven search while keeping the two environments behaving
 * identically without build-time configuration.
 */

import { API_BASE_URL } from "../config/env";

let reachable: Promise<boolean> | null = null;

export function isApiReachable(): Promise<boolean> {
  if (!reachable) {
    reachable = fetch(`${API_BASE_URL}/health`, { headers: { Accept: "application/json" } })
      .then((response) => response.ok)
      .catch(() => false);
  }
  return reachable;
}

/** Test-only hook to reset the cached probe between cases. */
export function resetApiReachability(): void {
  reachable = null;
}
