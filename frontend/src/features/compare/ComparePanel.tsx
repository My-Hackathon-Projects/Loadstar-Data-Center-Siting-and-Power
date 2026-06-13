import { useUiStore } from "../../hooks/useUiStore";
import {
  formatCarbon,
  formatEurPerMwh,
  formatMw,
  formatPercent,
} from "../../lib/formatters";
import { useCompareSites } from "../../lib/queries";

export function ComparePanel() {
  const cellIds = useUiStore((state) => state.comparisonCellIds);
  const clearComparison = useUiStore((state) => state.clearComparison);
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);
  const query = useCompareSites({ cell_ids: cellIds });
  const sites = query.data?.sites ?? [];

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Comparison</h2>
          <p className="mt-1 text-sm text-slate-600">
            {cellIds.length} cells pinned
          </p>
        </div>
        <button
          className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 disabled:text-slate-400"
          disabled={cellIds.length === 0}
          type="button"
          onClick={clearComparison}
        >
          Clear
        </button>
      </div>
      {cellIds.length < 2 ? (
        <p className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
          Add at least two ranked cells to compare siting metrics.
        </p>
      ) : null}
      {query.isError ? (
        <p className="mt-3 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">
          Comparison could not be loaded.
        </p>
      ) : null}
      {sites.length > 0 ? (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[520px] border-separate border-spacing-0 text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-normal text-slate-500">
                <th className="border-b border-slate-200 py-2 pr-3 font-medium">
                  Cell
                </th>
                <th className="border-b border-slate-200 px-3 py-2 font-medium">
                  Headroom
                </th>
                <th className="border-b border-slate-200 px-3 py-2 font-medium">
                  Price
                </th>
                <th className="border-b border-slate-200 px-3 py-2 font-medium">
                  Carbon
                </th>
                <th className="border-b border-slate-200 px-3 py-2 font-medium">
                  Land
                </th>
                <th className="border-b border-slate-200 py-2 pl-3 font-medium">
                  ML
                </th>
              </tr>
            </thead>
            <tbody>
              {sites.map((site) => (
                <tr className="align-top" key={site.cell_id}>
                  <td className="border-b border-slate-100 py-2 pr-3">
                    <button
                      className="text-left font-medium text-cyan-800 hover:underline"
                      type="button"
                      onClick={() => setSelectedCellId(site.cell_id)}
                    >
                      {site.region_name}
                    </button>
                    <span className="block text-xs text-slate-500">
                      {site.country_code}
                    </span>
                  </td>
                  <td className="border-b border-slate-100 px-3 py-2">
                    {formatMw(site.headroom_mw)}
                  </td>
                  <td className="border-b border-slate-100 px-3 py-2">
                    {formatEurPerMwh(site.mean_price_eur_mwh)}
                  </td>
                  <td className="border-b border-slate-100 px-3 py-2">
                    {formatCarbon(site.carbon_intensity_g_kwh)}
                  </td>
                  <td className="border-b border-slate-100 px-3 py-2">
                    {formatPercent(site.buildable_fraction)}
                  </td>
                  <td className="border-b border-slate-100 py-2 pl-3">
                    {formatPercent(site.lightgbm_score)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
