import { useMutation, useQuery } from "@tanstack/react-query";

import { explainSite } from "../api/agent";
import { getAssumptions } from "../api/assumptions";
import { getLayer } from "../api/layers";
import { optimizeSupplyMix } from "../api/optimization";
import { compareSites, getSite, searchSites } from "../api/sites";
import type {
  CompareRequest,
  ExplainRequest,
  OptimizeRequest,
  SearchRequest,
} from "../types/api";

export function useSearchSites(request: SearchRequest) {
  return useQuery({
    queryKey: ["sites", "search", request],
    queryFn: () => searchSites(request),
  });
}

export function useSiteDetail(cellId: string | null) {
  return useQuery({
    enabled: Boolean(cellId),
    queryKey: ["sites", "detail", cellId],
    queryFn: () => getSite(cellId ?? ""),
  });
}

export function useLayer(layerName: string) {
  return useQuery({
    queryKey: ["layers", layerName],
    queryFn: () => getLayer(layerName),
  });
}

export function useCompareSites(request: CompareRequest) {
  return useQuery({
    enabled: request.cell_ids.length >= 2,
    queryKey: ["sites", "compare", request.cell_ids],
    queryFn: () => compareSites(request),
  });
}

export function useAssumptions() {
  return useQuery({
    queryKey: ["assumptions"],
    queryFn: getAssumptions,
  });
}

export function useOptimizeSupplyMix() {
  return useMutation({
    mutationFn: (request: OptimizeRequest) => optimizeSupplyMix(request),
  });
}

export function useExplainSite() {
  return useMutation({
    mutationFn: (request: ExplainRequest) => explainSite(request),
  });
}
