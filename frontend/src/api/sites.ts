import type {
  CompareRequest,
  CompareResponse,
  SearchRequest,
  SearchResponse,
  SiteDetailResponse,
} from "../types/api";
import {
  compareSitesLocal,
  getSiteLocal,
  searchSitesLocal,
} from "../lib/siteEngine";
import { requestJson } from "./client";
import { isApiReachable } from "./dataSource";
import { loadSites } from "./staticData";

/**
 * Search/detail/compare are deterministic reads. When the API is up (local
 * dev) they go to the live engine; on the static deployment they run in the
 * browser against the committed dataset using the same scoring logic. Both
 * paths return the identical response shape.
 */

/** POST `/sites/search` and return the ranked site list. */
export async function searchSites(payload: SearchRequest): Promise<SearchResponse> {
  if (await isApiReachable()) {
    return requestJson<SearchResponse>("/sites/search", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
  return searchSitesLocal(payload, await loadSites());
}

/** GET `/sites/{cellId}` and return the full site detail payload. */
export async function getSite(cellId: string): Promise<SiteDetailResponse> {
  if (await isApiReachable()) {
    return requestJson<SiteDetailResponse>(`/sites/${cellId}`);
  }
  return getSiteLocal(cellId, await loadSites());
}

/** POST `/sites/compare` and return site feature rows in request order. */
export async function compareSites(payload: CompareRequest): Promise<CompareResponse> {
  if (await isApiReachable()) {
    return requestJson<CompareResponse>("/sites/compare", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
  return compareSitesLocal(payload, await loadSites());
}
