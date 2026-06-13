import type { AssumptionsResponse } from "../types/api";
import { requestJson } from "./client";

/** GET `/assumptions` and return public model assumptions. */
export function getAssumptions(): Promise<AssumptionsResponse> {
  return requestJson<AssumptionsResponse>("/assumptions");
}
