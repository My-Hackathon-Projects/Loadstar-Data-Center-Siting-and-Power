import type { OptimizeRequest, SupplyMixResponse } from "../types/api";
import { requestJson } from "./client";

/** POST `/optimize/supply-mix` and return the chart-ready supply-mix response. */
export function optimizeSupplyMix(
  payload: OptimizeRequest,
): Promise<SupplyMixResponse> {
  return requestJson<SupplyMixResponse>("/optimize/supply-mix", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
