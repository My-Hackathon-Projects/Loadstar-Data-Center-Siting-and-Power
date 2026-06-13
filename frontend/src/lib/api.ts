import { API_BASE_URL } from "../config/env";
import type {
  ApiErrorResponse,
  OptimizeRequest,
  SearchRequest,
  SearchResponse,
  SiteDetailResponse,
  SupplyMixResponse,
} from "../types/api";

/** Low-level JSON fetch wrapper. Throws on non-2xx; callers handle the error. */
async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
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

/** POST `/sites/search` and return the ranked site list. */
export function searchSites(payload: SearchRequest): Promise<SearchResponse> {
  return requestJson<SearchResponse>("/sites/search", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** GET `/sites/{cellId}` and return the full site detail payload. */
export function getSite(cellId: string): Promise<SiteDetailResponse> {
  return requestJson<SiteDetailResponse>(`/sites/${cellId}`);
}

/** POST `/optimize/supply-mix` and return the chart-ready supply-mix response. */
export function optimizeSupplyMix(
  payload: OptimizeRequest,
): Promise<SupplyMixResponse> {
  return requestJson<SupplyMixResponse>("/optimize/supply-mix", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
