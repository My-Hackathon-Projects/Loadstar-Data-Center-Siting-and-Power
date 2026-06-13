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
    <section>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="eyebrow">comparison</p>
          <h2 className="mt-1 text-lg text-primary">{cellIds.length} pinned</h2>
        </div>
        <button
          className="rounded-md border border-subtle px-3 py-1.5 text-sm text-dim transition-colors hover:text-primary disabled:opacity-40"
          disabled={cellIds.length === 0}
          type="button"
          onClick={clearComparison}
        >
          Clear
        </button>
      </div>
      {cellIds.length < 2 ? (
        <p className="mt-3 rounded-lg border border-subtle p-3 text-sm text-dim">
          Add at least two ranked cells to compare siting metrics.
        </p>
      ) : null}
      {query.isError ? (
        <p className="mt-3 rounded-lg border border-danger p-3 text-sm text-danger">
          Comparison could not be loaded.
        </p>
      ) : null}
      {sites.length > 0 ? (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[520px] border-separate border-spacing-0 text-left text-sm">
            <thead>
              <tr className="text-xs lowercase tracking-wide text-dim">
                <th className="border-b border-subtle py-2 pr-3 font-medium">
                  cell
                </th>
                <th className="border-b border-subtle px-3 py-2 font-medium">
                  headroom
                </th>
                <th className="border-b border-subtle px-3 py-2 font-medium">
                  price
                </th>
                <th className="border-b border-subtle px-3 py-2 font-medium">
                  carbon
                </th>
                <th className="border-b border-subtle px-3 py-2 font-medium">
                  land
                </th>
                <th className="border-b border-subtle py-2 pl-3 font-medium">
                  ml
                </th>
              </tr>
            </thead>
            <tbody>
              {sites.map((site) => (
                <tr className="align-top" key={site.cell_id}>
                  <td className="border-b border-subtle py-2 pr-3">
                    <button
                      className="text-left font-medium text-accent hover:underline"
                      type="button"
                      onClick={() => setSelectedCellId(site.cell_id)}
                    >
                      {site.region_name}
                    </button>
                    <span className="block text-xs text-dim">
                      {site.country_code}
                    </span>
                  </td>
                  <td className="border-b border-subtle px-3 py-2 text-primary">
                    {formatMw(site.headroom_mw)}
                  </td>
                  <td className="border-b border-subtle px-3 py-2 text-primary">
                    {formatEurPerMwh(site.mean_price_eur_mwh)}
                  </td>
                  <td className="border-b border-subtle px-3 py-2 text-primary">
                    {formatCarbon(site.carbon_intensity_g_kwh)}
                  </td>
                  <td className="border-b border-subtle px-3 py-2 text-primary">
                    {formatPercent(site.buildable_fraction)}
                  </td>
                  <td className="border-b border-subtle py-2 pl-3 text-primary">
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
