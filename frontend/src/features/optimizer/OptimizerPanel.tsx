import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useUiStore } from "../../hooks/useUiStore";
import { formatCarbon, formatEurPerMwh, formatPercent } from "../../lib/formatters";
import { useOptimizeSupplyMix } from "../../lib/queries";

export function OptimizerPanel() {
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const powerMw = useUiStore((state) => state.powerMw);
  const loadProfile = useUiStore((state) => state.loadProfile);
  const mutation = useOptimizeSupplyMix();
  const result = mutation.data;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-base font-semibold">Pareto Frontier</h2>
      <button
        className="mt-3 rounded-md bg-cyan-700 px-4 py-2 text-sm text-white disabled:bg-slate-400"
        disabled={!selectedCellId || mutation.isPending}
        type="button"
        onClick={() => {
          if (selectedCellId) {
            // load_mw mirrors the search MW so the optimizer matches the size
            // currently being explored on the map and ranked list.
            mutation.mutate({
              cell_id: selectedCellId,
              load_mw: powerMw,
              load_profile: loadProfile
            });
          }
        }}
      >
        Run Optimizer
      </button>
      <div className="mt-3 h-44 rounded-md border border-slate-200 p-2">
        <ResponsiveContainer height="100%" width="100%">
          <LineChart data={result?.pareto_frontier ?? []}>
            <XAxis dataKey="effective_carbon_g_kwh" />
            <YAxis dataKey="effective_cost_eur_mwh" />
            <Tooltip />
            <Line
              dataKey="effective_cost_eur_mwh"
              stroke="#176b87"
              strokeWidth={3}
              type="monotone"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {result ? (
        <p className="mt-3 text-sm text-slate-600">
          Cost {formatEurPerMwh(result.effective_cost_eur_mwh)} · Carbon{" "}
          {formatCarbon(result.effective_carbon_g_kwh)} · 24/7 CFE{" "}
          {formatPercent(result.hourly_24_7_cfe_share)}
        </p>
      ) : null}
    </section>
  );
}
