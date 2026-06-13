import { useEffect, useMemo } from "react";

import {
  SEARCH_TOP_K_OPTIONS,
  WORKLOAD_TYPE_OPTIONS,
} from "../../config/defaults";
import { useUiStore } from "../../hooks/useUiStore";
import { useSearchSites } from "../../lib/queries";
import type { SearchRequest } from "../../types/api";
import { RankedSites } from "./RankedSites";

export function SearchPanel() {
  const powerMw = useUiStore((state) => state.powerMw);
  const workloadType = useUiStore((state) => state.workloadType);
  const topK = useUiStore((state) => state.topK);
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);
  const setSearchParams = useUiStore((state) => state.setSearchParams);
  const query = useSearchSites({
    power_mw: powerMw,
    workload_type: workloadType,
    top_k: topK,
  });
  const results = useMemo(
    () => query.data?.results ?? [],
    [query.data?.results],
  );

  useEffect(() => {
    const firstCell = results[0]?.site.cell_id;
    const selectedStillVisible = results.some(
      (result) => result.site.cell_id === selectedCellId,
    );
    if (firstCell && (!selectedCellId || !selectedStillVisible)) {
      setSelectedCellId(firstCell);
    }
    if (!firstCell && selectedCellId) {
      setSelectedCellId(null);
    }
  }, [results, selectedCellId, setSelectedCellId]);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-sm text-slate-600">
          MW
          <input
            className="w-28 rounded-md border border-slate-300 px-3 py-2 text-slate-900"
            min={1}
            type="number"
            value={powerMw}
            onChange={(event) =>
              setSearchParams({
                powerMw: Math.max(1, Number(event.target.value) || 1),
              })
            }
          />
        </label>
        <label className="grid gap-1 text-sm text-slate-600">
          Workload
          <select
            className="w-36 rounded-md border border-slate-300 px-3 py-2 text-slate-900"
            value={workloadType}
            onChange={(event) =>
              setSearchParams({
                workloadType: event.target.value as SearchRequest["workload_type"],
              })
            }
          >
            {WORKLOAD_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-slate-600">
          Results
          <select
            className="w-24 rounded-md border border-slate-300 px-3 py-2 text-slate-900"
            value={topK}
            onChange={(event) =>
              setSearchParams({
                topK: Number(event.target.value),
              })
            }
          >
            {SEARCH_TOP_K_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="mt-3 grid gap-2">
        {query.data?.warnings.map((warning) => (
          <div
            className="rounded-md border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800"
            key={warning.code}
          >
            {warning.message}
          </div>
        ))}
        {query.isError ? (
          <div className="rounded-md border border-rose-300 bg-rose-50 p-2 text-sm text-rose-800">
            {query.error.message}
          </div>
        ) : null}
      </div>
      <RankedSites isLoading={query.isLoading} results={results} />
    </section>
  );
}
