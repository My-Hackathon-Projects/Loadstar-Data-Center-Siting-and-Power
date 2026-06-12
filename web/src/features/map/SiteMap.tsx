import { useSearchSites } from "../../lib/queries";
import { useUiStore } from "../../hooks/useUiStore";
import type { RankedSite } from "../../types/api";

function mapPosition(site: RankedSite["site"]) {
  const minLon = -11;
  const maxLon = 25;
  const minLat = 47;
  const maxLat = 67;
  return {
    x: ((site.longitude - minLon) / (maxLon - minLon)) * 92 + 4,
    y: (1 - (site.latitude - minLat) / (maxLat - minLat)) * 88 + 6
  };
}

export function SiteMap() {
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);
  const query = useSearchSites({ power_mw: 280, workload_type: "training", top_k: 8 });
  const results = query.data?.results ?? [];

  return (
    <div className="relative min-h-[640px] overflow-hidden rounded-lg border border-slate-200 bg-slate-100">
      {results.map((result) => {
        const { x, y } = mapPosition(result.site);
        return (
          <div key={result.site.cell_id}>
            <button
              aria-label={`${result.site.region_name} score ${result.composite_score}`}
              className="absolute h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white bg-cyan-700 shadow-md"
              style={{ left: `${x}%`, top: `${y}%` }}
              type="button"
              onClick={() => setSelectedCellId(result.site.cell_id)}
            />
            <span
              className="absolute translate-x-3 -translate-y-1/2 rounded bg-white/85 px-2 py-1 text-xs"
              style={{ left: `${x}%`, top: `${y}%` }}
            >
              {result.site.region_name} ({result.site.country_code})
            </span>
          </div>
        );
      })}
    </div>
  );
}
