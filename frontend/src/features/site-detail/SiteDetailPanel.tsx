import { Metric } from "../../components/Metric";
import { useUiStore } from "../../hooks/useUiStore";
import {
  formatCarbon,
  formatCoolingIndex,
  formatDistanceKm,
  formatEurPerMwh,
  formatKv,
  formatMva,
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
  const nearestKv = site?.nearest_substation_kv ?? null;
  const nearestDistance = site?.nearest_substation_distance_km ?? null;
  const nearestCapacity = site?.nearest_substation_capacity_mva ?? null;
  const hasGridContext = nearestKv !== null && nearestDistance !== null;

  return (
    <section>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">specifications</p>
          <h2 className="mt-1 text-lg text-primary">Site detail</h2>
          {site ? (
            <p className="mt-1 text-sm text-dim">
              {site.region_name}, {site.country_code}
            </p>
          ) : null}
        </div>
        {query.isFetching ? (
          <span className="rounded-md border border-subtle px-2 py-1 text-xs text-dim">
            Updating
          </span>
        ) : null}
      </div>
      {!site ? (
        <p className="mt-3 text-sm text-dim">Select a ranked site.</p>
      ) : (
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-2">
            <Metric label="cell" value={site.cell_id} />
            <Metric label="headroom" value={formatMw(site.headroom_mw)} />
            <Metric
              label="price"
              value={formatEurPerMwh(site.mean_price_eur_mwh)}
            />
            <Metric
              label="carbon"
              value={formatCarbon(site.carbon_intensity_g_kwh)}
            />
            <Metric
              label="congestion"
              value={site.congestion_index.toFixed(2)}
            />
            <Metric
              label="buildable"
              value={formatPercent(site.buildable_fraction)}
            />
            <Metric
              label="ml viability"
              value={formatPercent(site.lightgbm_score)}
            />
            <Metric
              label="dc similarity"
              value={formatPercent(site.dc_similarity)}
            />
            <Metric
              label="fiber distance"
              value={formatDistanceKm(site.dist_fiber_km)}
            />
            <Metric
              label="hv distance"
              value={formatDistanceKm(site.dist_hv_substation_km)}
            />
          </div>
          <div>
            <p className="eyebrow">curated model inputs</p>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <Metric
                label="water dist"
                value={formatDistanceKm(site.water_dist_km)}
              />
              <Metric
                label="cooling load"
                value={formatCoolingIndex(site.cooling_degree_proxy)}
              />
            </div>
          </div>
          {hasGridContext ? (
            <div>
              <p className="eyebrow">nearest substation</p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <Metric
                  label="voltage"
                  value={formatKv(nearestKv as number)}
                />
                <Metric
                  label="distance"
                  value={formatDistanceKm(nearestDistance as number)}
                />
                {nearestCapacity !== null ? (
                  <Metric
                    label="connected capacity"
                    value={formatMva(nearestCapacity)}
                  />
                ) : null}
              </div>
            </div>
          ) : null}
          <div>
            <p className="eyebrow">viability drivers</p>
            <div className="mt-2 grid gap-2">
              {shapEntries.map(([factor, value]) => (
                <div
                  className="flex items-center justify-between gap-3 rounded-lg border border-subtle px-3 py-2 text-sm"
                  key={factor}
                >
                  <span className="break-words text-dim">
                    {factor.replaceAll("_", " ")}
                  </span>
                  <span className={value >= 0 ? "text-positive" : "text-danger"}>
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
