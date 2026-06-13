import { API_BASE_URL } from "../config/env";
import type { ApiErrorResponse } from "../types/api";

/** Low-level JSON fetch wrapper. Throws on non-2xx; callers handle the error. */
export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return (await response.json()) as T;
}

async function responseErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as Partial<ApiErrorResponse>;
    const message = payload.detail?.message;
    if (message) {
      return message;
    }
  } catch {
    // Keep the caller-facing error deterministic when the response is not JSON.
  }
  return `Request failed: ${response.status}`;
}
