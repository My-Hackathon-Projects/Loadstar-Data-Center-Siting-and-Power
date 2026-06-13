import { LOAD_PROFILE_OPTIONS } from "../../config/defaults";
import { useUiStore } from "../../hooks/useUiStore";
import {
  formatCarbon,
  formatEurPerMwh,
  formatPercent,
} from "../../lib/formatters";
import { useOptimizeSupplyMix } from "../../lib/queries";
import type { OptimizeRequest } from "../../types/api";
import { dispatchChartRows } from "./optimizerCharts";
import { portfolioRows, summaryMetric } from "./optimizerSummary";
import { DispatchChart, ParetoChart } from "./SupplyMixCharts";

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
                loadProfile: event.target.value as OptimizeRequest["load_profile"],
              })
            }
          >
            {LOAD_PROFILE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
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
      <ParetoChart points={result?.pareto_frontier ?? []} />
      <DispatchChart rows={dispatchRows} />
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
            {portfolioRows(result.recommended_portfolio).map(
              ({ key, label, value }) => (
                <div
                  className="rounded-md border border-slate-200 px-3 py-2"
                  key={key}
                >
                  <span className="block text-xs text-slate-500">{label}</span>
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
