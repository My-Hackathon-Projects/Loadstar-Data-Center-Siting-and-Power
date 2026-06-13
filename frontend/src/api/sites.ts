import type {
  CompareRequest,
  CompareResponse,
  SearchRequest,
  SearchResponse,
  SiteDetailResponse,
} from "../types/api";
import { requestJson } from "./client";

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

/** POST `/sites/compare` and return site feature rows in request order. */
export function compareSites(payload: CompareRequest): Promise<CompareResponse> {
  return requestJson<CompareResponse>("/sites/compare", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
