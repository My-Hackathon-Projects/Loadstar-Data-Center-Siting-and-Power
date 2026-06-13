import { useMutation, useQuery } from "@tanstack/react-query";

import { chatAgent, explainSite } from "../api/agent";
import { getAssumptions } from "../api/assumptions";
import { getLayer } from "../api/layers";
import { optimizeSupplyMix } from "../api/optimization";
import { compareSites, getSite, searchSites } from "../api/sites";
import type {
  AgentChatRequest,
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

/**
 * Auto-running supply-mix optimization for the selected cell. Keyed on the cell
 * and load inputs so the result is cached and refetched when the selection
 * changes; this feeds the effective-cost and CFE-share stat cards (and the
 * optimizer panel) without a manual trigger.
 */
export function useSupplyMix(
  cellId: string | null,
  loadMw: number,
  loadProfile: OptimizeRequest["load_profile"],
) {
  return useQuery({
    enabled: Boolean(cellId),
    queryKey: ["optimize", "supply-mix", cellId, loadMw, loadProfile],
    queryFn: () =>
      optimizeSupplyMix({
        cell_id: cellId ?? "",
        load_mw: loadMw,
        load_profile: loadProfile,
      }),
  });
}

export function useExplainSite() {
  return useMutation({
    mutationFn: (request: ExplainRequest) => explainSite(request),
  });
}

export function useChatAgent() {
  return useMutation({
    mutationFn: (request: AgentChatRequest) => chatAgent(request),
  });
}
