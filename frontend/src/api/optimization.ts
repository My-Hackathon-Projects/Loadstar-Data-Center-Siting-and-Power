import type { OptimizeRequest, SupplyMixResponse } from "../types/api";
import { requestJson } from "./client";
import { isApiReachable } from "./dataSource";

/** Surfaced to callers (panel + stat cards) when the optimizer cannot run. */
export const OPTIMIZER_UNAVAILABLE_MESSAGE =
  "The supply-mix optimizer runs on the live engine (a 24-hour linear program), " +
  "which is not available on this static deployment. Run the API locally to use it.";

/**
 * POST `/optimize/supply-mix`. The optimizer is a scipy linear program, so it
 * has no in-browser fallback. When no API is reachable this rejects with a
 * clear message; the dashboard renders that state instead of crashing, and the
 * optimizer stat cards fall back to their placeholder.
 */
export async function optimizeSupplyMix(
  payload: OptimizeRequest,
): Promise<SupplyMixResponse> {
  if (await isApiReachable()) {
    return requestJson<SupplyMixResponse>("/optimize/supply-mix", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
  throw new Error(OPTIMIZER_UNAVAILABLE_MESSAGE);
}
