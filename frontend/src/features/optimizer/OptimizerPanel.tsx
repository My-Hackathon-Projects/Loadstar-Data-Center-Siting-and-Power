import { LOAD_PROFILE_OPTIONS } from "../../config/defaults";
import { useUiStore } from "../../hooks/useUiStore";
import {
  formatCarbon,
  formatEurPerMwh,
  formatPercent,
} from "../../lib/formatters";
import { useSupplyMix } from "../../lib/queries";
import type { OptimizeRequest } from "../../types/api";
import { dispatchChartRows } from "./optimizerCharts";
import { portfolioRows, summaryMetric } from "./optimizerSummary";
import { DispatchChart, ParetoChart } from "./SupplyMixCharts";

export function OptimizerPanel() {
  const loadProfile = useUiStore((state) => state.loadProfile);
  const powerMw = useUiStore((state) => state.powerMw);
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const setSearchParams = useUiStore((state) => state.setSearchParams);
  // Auto-runs whenever the selected cell or load inputs change; no manual trigger.
  const query = useSupplyMix(selectedCellId, powerMw, loadProfile);
  const result = query.data;
  const dispatchRows = dispatchChartRows(result?.dispatch_preview ?? []);

  return (
    <section>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">supply mix</p>
          <h2 className="mt-1 text-lg text-primary">Pareto and dispatch</h2>
        </div>
        <label className="grid gap-1 text-xs lowercase tracking-wide text-dim">
          load profile
          <select
            className="w-40 rounded-md border border-subtle bg-void px-3 py-2 text-sm text-primary outline-none focus:border-accent"
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
      {!selectedCellId ? (
        <p className="mt-3 text-sm text-dim">
          Select a ranked cell to optimize its supply mix.
        </p>
      ) : null}
      {query.isPending && selectedCellId ? (
        <p className="mt-3 text-sm text-dim">Optimizing supply mix...</p>
      ) : null}
      {query.isError ? (
        <p className="mt-3 rounded-lg border border-danger p-3 text-sm text-danger">
          {query.error.message}
        </p>
      ) : null}
      {result ? (
        <>
          <ParetoChart points={result.pareto_frontier} />
          <DispatchChart rows={dispatchRows} />
          <div className="mt-3 space-y-3 text-sm text-dim">
            <p>
              Cost{" "}
              <span className="text-primary">
                {formatEurPerMwh(result.effective_cost_eur_mwh)}
              </span>{" "}
              · Carbon{" "}
              <span className="text-primary">
                {formatCarbon(result.effective_carbon_g_kwh)}
              </span>{" "}
              · 24/7 CFE{" "}
              <span className="text-primary">
                {formatPercent(result.hourly_24_7_cfe_share)}
              </span>
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
                    className="rounded-lg border border-subtle px-3 py-2"
                    key={key}
                  >
                    <span className="block text-xs lowercase text-dim">
                      {label}
                    </span>
                    <span className="text-sm text-primary">
                      {formatPercent(value)}
                    </span>
                  </div>
                ),
              )}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
