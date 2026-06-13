import type { AgentChatResponse } from "../types/api";

/**
 * Cross-screen handoff for the landing voice search. The greeting screen runs
 * the agent live, persists the response here, and advances to the dashboard.
 * The dashboard mounts, consumes the handoff, seeds the chat list with both
 * sides of the turn, and applies any search action — without re-calling the
 * backend. A separate {@link savePendingFredPrompt} fallback covers the error
 * case where the landing call failed and the dashboard must retry.
 */

const PENDING_USER_KEY = "loadstar:fred-pending-user-message";
const PENDING_RESPONSE_KEY = "loadstar:fred-pending-agent-response";

export interface FredHandoff {
  userMessage: string;
  response: AgentChatResponse;
}

function sessionStorageSafe(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function savePendingAgentHandoff(
  userMessage: string,
  response: AgentChatResponse,
): void {
  const trimmed = userMessage.trim();
  const storage = sessionStorageSafe();
  if (!trimmed || storage === null) {
    return;
  }
  try {
    storage.setItem(PENDING_USER_KEY, trimmed);
    storage.setItem(PENDING_RESPONSE_KEY, JSON.stringify(response));
  } catch {
    // Quota or serialization error — drop the handoff silently. The
    // dashboard will simply render the INTRO message and let the user type.
    storage.removeItem(PENDING_USER_KEY);
    storage.removeItem(PENDING_RESPONSE_KEY);
  }
}

export function consumePendingAgentHandoff(): FredHandoff | null {
  const storage = sessionStorageSafe();
  if (storage === null) {
    return null;
  }
  const userMessage = storage.getItem(PENDING_USER_KEY);
  const rawResponse = storage.getItem(PENDING_RESPONSE_KEY);
  storage.removeItem(PENDING_USER_KEY);
  storage.removeItem(PENDING_RESPONSE_KEY);
  if (userMessage === null || rawResponse === null) {
    return null;
  }
  try {
    const response = JSON.parse(rawResponse) as AgentChatResponse;
    return { userMessage: userMessage.trim(), response };
  } catch {
    return null;
  }
}
