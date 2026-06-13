import { Metric } from "../../components/Metric";
import { useUiStore } from "../../hooks/useUiStore";
import {
  formatCarbon,
  formatDistanceKm,
  formatEurPerMwh,
  formatMw,
  formatPercent,
} from "../../lib/formatters";
import { useSiteDetail } from "../../lib/queries";

export function SiteDetailPanel() {
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const query = useSiteDetail(selectedCellId);
  const site = query.data?.site;
  const shapEntries = Object.entries(site?.shap_values ?? {})
    .sort((left, right) => Math.abs(right[1]) - Math.abs(left[1]))
    .slice(0, 4);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Site Detail</h2>
          {site ? (
            <p className="mt-1 text-sm text-slate-600">
              {site.region_name}, {site.country_code}
            </p>
          ) : null}
        </div>
        {query.isFetching ? (
          <span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-500">
            Updating
          </span>
        ) : null}
      </div>
      {!site ? (
        <p className="mt-3 text-sm text-slate-500">Select a ranked site.</p>
      ) : (
        <div className="mt-3 space-y-4">
          <div className="grid grid-cols-2 gap-2">
            <Metric label="Cell" value={site.cell_id} />
            <Metric label="Headroom" value={formatMw(site.headroom_mw)} />
            <Metric
              label="Price"
              value={formatEurPerMwh(site.mean_price_eur_mwh)}
            />
            <Metric
              label="Carbon"
              value={formatCarbon(site.carbon_intensity_g_kwh)}
            />
            <Metric
              label="Congestion"
              value={site.congestion_index.toFixed(2)}
            />
            <Metric
              label="Buildable"
              value={formatPercent(site.buildable_fraction)}
            />
            <Metric
              label="ML viability"
              value={formatPercent(site.lightgbm_score)}
            />
            <Metric
              label="DC similarity"
              value={formatPercent(site.dc_similarity)}
            />
            <Metric
              label="Fiber distance"
              value={formatDistanceKm(site.dist_fiber_km)}
            />
            <Metric
              label="HV distance"
              value={formatDistanceKm(site.dist_hv_substation_km)}
            />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Viability Drivers
            </h3>
            <div className="mt-2 grid gap-2">
              {shapEntries.map(([factor, value]) => (
                <div
                  className="flex items-center justify-between gap-3 rounded-md border border-slate-200 px-3 py-2 text-sm"
                  key={factor}
                >
                  <span className="break-words text-slate-700">
                    {factor.replaceAll("_", " ")}
                  </span>
                  <span
                    className={value >= 0 ? "text-cyan-700" : "text-rose-700"}
                  >
                    {value >= 0 ? "+" : ""}
                    {value.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
