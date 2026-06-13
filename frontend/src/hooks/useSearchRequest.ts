import { useMemo } from "react";

import type { SearchRequest, Weights } from "../types/api";
import { useUiStore } from "./useUiStore";

/**
 * Rescale weights to sum to 1. The engine composite is a weighted sum, so this
 * keeps the score in 0..1 (renders as a percentage) without changing the
 * ranking, which is invariant under a uniform rescale.
 */
function normalizeWeights(weights: Weights): Weights {
  const entries = Object.entries(weights);
  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  if (total <= 0) {
    return weights;
  }
  return Object.fromEntries(
    entries.map(([key, value]) => [key, value / total]),
  ) as Weights;
}

/**
 * The single SearchRequest derived from the UI store, shared by the map and the
 * specifications bar so both query the same cache key. Weights and country
 * filter are already-supported optional `SearchRequest` fields; including them
 * lets the sliders, filter chips, and Fred's agent search drive the results.
 */
export function useSearchRequest(): SearchRequest {
  const powerMw = useUiStore((state) => state.powerMw);
  const workloadType = useUiStore((state) => state.workloadType);
  const topK = useUiStore((state) => state.topK);
  const weights = useUiStore((state) => state.weights);
  const countryFilter = useUiStore((state) => state.countryFilter);

  return useMemo(
    () => ({
      power_mw: powerMw,
      workload_type: workloadType,
      top_k: topK,
      weights: normalizeWeights(weights),
      country_filter: countryFilter.length > 0 ? countryFilter : null,
    }),
    [powerMw, workloadType, topK, weights, countryFilter],
  );
}
