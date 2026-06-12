import { Metric } from "../../components/Metric";
import { useUiStore } from "../../hooks/useUiStore";
import { formatCarbon, formatDistanceKm, formatEurPerMwh } from "../../lib/formatters";
import { useSiteDetail } from "../../lib/queries";

export function SiteDetailPanel() {
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const query = useSiteDetail(selectedCellId);
  const site = query.data?.site;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-base font-semibold">Site Detail</h2>
      {!site ? (
        <p className="mt-3 text-sm text-slate-500">Select a ranked site.</p>
      ) : (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Metric label="Cell" value={site.cell_id} />
          <Metric label="Country" value={site.country_code} />
          <Metric label="Price" value={formatEurPerMwh(site.mean_price_eur_mwh)} />
          <Metric label="Carbon" value={formatCarbon(site.carbon_intensity_g_kwh)} />
          <Metric label="Congestion" value={`${site.congestion_index}`} />
          <Metric label="Fiber distance" value={formatDistanceKm(site.dist_fiber_km)} />
        </div>
      )}
    </section>
  );
}
