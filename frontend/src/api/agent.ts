import type {
  AgentChatRequest,
  AgentChatResponse,
  ExplainRequest,
  ExplainResponse,
} from "../types/api";
import { requestJson } from "./client";

/** POST `/agent/explain` and return the LLM-or-template explanation payload. */
export function explainSite(payload: ExplainRequest): Promise<ExplainResponse> {
  return requestJson<ExplainResponse>("/agent/explain", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** POST `/agent/chat`: Fred runs a real search and returns a dashboard action. */
export function chatAgent(payload: AgentChatRequest): Promise<AgentChatResponse> {
  return requestJson<AgentChatResponse>("/agent/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
