import type {
  OptimizeRequest,
  SearchRequest,
  SearchResponse,
  SiteDetailResponse,
  SupplyMixResponse
} from "../types/api";

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function searchSites(payload: SearchRequest): Promise<SearchResponse> {
  return requestJson<SearchResponse>("/sites/search", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getSite(cellId: string): Promise<SiteDetailResponse> {
  return requestJson<SiteDetailResponse>(`/sites/${cellId}`);
}

export function optimizeSupplyMix(payload: OptimizeRequest): Promise<SupplyMixResponse> {
  return requestJson<SupplyMixResponse>("/optimize/supply-mix", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
