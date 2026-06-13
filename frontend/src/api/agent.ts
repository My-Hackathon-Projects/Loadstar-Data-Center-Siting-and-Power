import type { ExplainRequest, ExplainResponse } from "../types/api";
import { requestJson } from "./client";

/** POST `/agent/explain` and return the LLM-or-template explanation payload. */
export function explainSite(payload: ExplainRequest): Promise<ExplainResponse> {
  return requestJson<ExplainResponse>("/agent/explain", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
