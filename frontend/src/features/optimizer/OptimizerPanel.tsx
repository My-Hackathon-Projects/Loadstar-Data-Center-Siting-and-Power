import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useUiStore } from "../../hooks/useUiStore";
import {
  formatCarbon,
  formatEurPerMwh,
  formatPercent,
} from "../../lib/formatters";
import { useOptimizeSupplyMix } from "../../lib/queries";
import { dispatchChartRows } from "./optimizerCharts";

export function OptimizerPanel() {
  const loadProfile = useUiStore((state) => state.loadProfile);
  const powerMw = useUiStore((state) => state.powerMw);
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const setSearchParams = useUiStore((state) => state.setSearchParams);
  const mutation = useOptimizeSupplyMix();
  const result = mutation.data;
  const dispatchRows = dispatchChartRows(result?.dispatch_preview ?? []);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Supply Mix</h2>
          <p className="mt-1 text-sm text-slate-600">
            Pareto frontier and 24-hour dispatch.
          </p>
        </div>
        <label className="grid gap-1 text-sm text-slate-600">
          Load profile
          <select
            className="w-40 rounded-md border border-slate-300 px-3 py-2 text-slate-900"
            value={loadProfile}
            onChange={(event) =>
              setSearchParams({
                loadProfile: event.target.value as
                  | "flat_24_7"
                  | "spiky_training",
              })
            }
          >
            <option value="flat_24_7">Flat 24/7</option>
            <option value="spiky_training">Spiky training</option>
          </select>
        </label>
      </div>
      <button
        className="mt-3 rounded-md bg-cyan-700 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-400"
        disabled={!selectedCellId || mutation.isPending}
        type="button"
        onClick={() => {
          if (selectedCellId) {
            mutation.mutate({
              cell_id: selectedCellId,
              load_mw: powerMw,
              load_profile: loadProfile,
            });
          }
        }}
      >
        {mutation.isPending ? "Optimizing..." : "Run Optimizer"}
      </button>
      {mutation.isError ? (
        <p className="mt-3 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">
          {mutation.error.message}
        </p>
      ) : null}
      <div className="mt-3 h-56 rounded-md border border-slate-200 p-2">
        <ResponsiveContainer height="100%" width="100%">
          <LineChart
            data={result?.pareto_frontier ?? []}
            margin={{ bottom: 16, left: 8, right: 18, top: 12 }}
          >
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" />
            <XAxis
              dataKey="effective_carbon_g_kwh"
              label={{ position: "insideBottom", value: "Carbon gCO2/kWh" }}
              tick={{ fontSize: 12 }}
            />
            <YAxis
              dataKey="effective_cost_eur_mwh"
              label={{ angle: -90, position: "insideLeft", value: "EUR/MWh" }}
              tick={{ fontSize: 12 }}
              width={52}
            />
            <Tooltip />
            <Line
              dataKey="effective_cost_eur_mwh"
              dot={{ r: 3 }}
              name="Cost"
              stroke="#0e7490"
              strokeWidth={3}
              type="monotone"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 h-56 rounded-md border border-slate-200 p-2">
        <ResponsiveContainer height="100%" width="100%">
          <LineChart
            data={dispatchRows}
            margin={{ bottom: 16, left: 8, right: 18, top: 12 }}
          >
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" />
            <XAxis
              dataKey="hour"
              label={{ position: "insideBottom", value: "Hour" }}
              tick={{ fontSize: 12 }}
            />
            <YAxis tick={{ fontSize: 12 }} width={52} />
            <Tooltip />
            <Legend verticalAlign="top" />
            <Line
              dataKey="load"
              dot={false}
              name="Load"
              stroke="#111827"
              strokeWidth={2}
            />
            <Line
              dataKey="grid"
              dot={false}
              name="Grid"
              stroke="#64748b"
              strokeWidth={2}
            />
            <Line
              dataKey="clean"
              dot={false}
              name="Clean"
              stroke="#15803d"
              strokeWidth={2}
            />
            <Line
              dataKey="battery"
              dot={false}
              name="Battery"
              stroke="#c2410c"
              strokeWidth={2}
            />
            <Line
              dataKey="backup"
              dot={false}
              name="Backup"
              stroke="#be123c"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {result ? (
        <div className="mt-3 space-y-3 text-sm text-slate-600">
          <p>
            Cost {formatEurPerMwh(result.effective_cost_eur_mwh)} · Carbon{" "}
            {formatCarbon(result.effective_carbon_g_kwh)} · 24/7 CFE{" "}
            {formatPercent(result.hourly_24_7_cfe_share)}
          </p>
          <p>
            Solver {result.solver_status} · Annual clean{" "}
            {formatPercent(result.annual_matched_clean_share)} · Battery{" "}
            {summaryMetric(
              result.dispatch_summary,
              "battery_power_capacity_mw",
            ).toFixed(1)}{" "}
            MW /{" "}
            {summaryMetric(
              result.dispatch_summary,
              "battery_energy_capacity_mwh",
            ).toFixed(1)}{" "}
            MWh
          </p>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(result.recommended_portfolio).map(
              ([key, value]) => (
                <div
                  className="rounded-md border border-slate-200 px-3 py-2"
                  key={key}
                >
                  <span className="block text-xs text-slate-500">
                    {formatPortfolioKey(key)}
                  </span>
                  <span className="text-sm text-slate-900">
                    {formatPercent(value)}
                  </span>
                </div>
              ),
            )}
          </div>
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-500">
          Select a cell and run the optimizer to populate cost, carbon,
          portfolio, and dispatch.
        </p>
      )}
    </section>
  );
}

function summaryMetric(summary: Record<string, number>, key: string): number {
  return summary[key] ?? 0;
}

function formatPortfolioKey(key: string): string {
  return key.replaceAll("_", " ");
}
