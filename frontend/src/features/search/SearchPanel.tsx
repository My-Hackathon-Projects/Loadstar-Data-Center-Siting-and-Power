import { useEffect, useState } from "react";

import { useSearchSites } from "../../lib/queries";
import { useUiStore } from "../../hooks/useUiStore";
import { RankedSites } from "./RankedSites";

export function SearchPanel() {
  const [powerMw, setPowerMw] = useState(280);
  const [workloadType, setWorkloadType] = useState<"training" | "inference" | "mixed">("training");
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);
  const query = useSearchSites({ power_mw: powerMw, workload_type: workloadType, top_k: 8 });

  useEffect(() => {
    const firstCell = query.data?.results[0]?.site.cell_id;
    if (firstCell) {
      setSelectedCellId(firstCell);
    }
  }, [query.data?.results, setSelectedCellId]);

  return (
    <div className="w-full max-w-xl">
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-sm text-slate-600">
          MW
          <input
            className="w-32 rounded-md border border-slate-300 px-3 py-2 text-slate-900"
            min={1}
            type="number"
            value={powerMw}
            onChange={(event) => setPowerMw(Number(event.target.value))}
          />
        </label>
        <label className="grid gap-1 text-sm text-slate-600">
          Workload
          <select
            className="w-36 rounded-md border border-slate-300 px-3 py-2 text-slate-900"
            value={workloadType}
            onChange={(event) =>
              setWorkloadType(event.target.value as "training" | "inference" | "mixed")
            }
          >
            <option value="training">Training</option>
            <option value="inference">Inference</option>
            <option value="mixed">Mixed</option>
          </select>
        </label>
      </div>
      <div className="mt-3 grid gap-2">
        {query.data?.warnings.map((warning) => (
          <div className="rounded-md border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800" key={warning.code}>
            {warning.message}
          </div>
        ))}
      </div>
      <RankedSites isLoading={query.isLoading} results={query.data?.results ?? []} />
    </div>
  );
}
