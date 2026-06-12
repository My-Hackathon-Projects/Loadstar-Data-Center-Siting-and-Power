import { useMutation, useQuery } from "@tanstack/react-query";

import { getSite, optimizeSupplyMix, searchSites } from "./api";
import type { OptimizeRequest, SearchRequest } from "../types/api";

export function useSearchSites(request: SearchRequest) {
  return useQuery({
    queryKey: ["sites", "search", request],
    queryFn: () => searchSites(request)
  });
}

export function useSiteDetail(cellId: string | null) {
  return useQuery({
    enabled: Boolean(cellId),
    queryKey: ["sites", "detail", cellId],
    queryFn: () => getSite(cellId ?? "")
  });
}

export function useOptimizeSupplyMix() {
  return useMutation({
    mutationFn: (request: OptimizeRequest) => optimizeSupplyMix(request)
  });
}
