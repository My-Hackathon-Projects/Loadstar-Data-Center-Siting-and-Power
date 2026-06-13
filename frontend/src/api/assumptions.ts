import { API_BASE_URL } from "../config/env";
import type { AssumptionsResponse } from "../types/api";
import { requestJson } from "./client";
import { isApiReachable } from "./dataSource";

/**
 * GET `/assumptions`, or the committed static asset when no API is reachable.
 * The static file is generated from the same backend payload by
 * `build_layer_assets`, so the panel is identical in both environments.
 */
export async function getAssumptions(): Promise<AssumptionsResponse> {
  if (await isApiReachable()) {
    return requestJson<AssumptionsResponse>("/assumptions");
  }
  const response = await fetch(`${API_BASE_URL}/data/assumptions.json`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Assumptions unavailable: ${response.status}`);
  }
  return (await response.json()) as AssumptionsResponse;
}
