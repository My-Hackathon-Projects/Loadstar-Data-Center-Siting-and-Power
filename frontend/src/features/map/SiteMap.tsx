import { useUiStore } from "../../hooks/useUiStore";
import { useSearchSites } from "../../lib/queries";
import type { RankedSite } from "../../types/api";

/**
 * Map (longitude, latitude) to a (left%, top%) coordinate inside the rendered
 * map container. The bounding box is the rough Europe envelope; this is a
 * placeholder visualization, not a real map projection.
 */
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
  const powerMw = useUiStore((state) => state.powerMw);
  const workloadType = useUiStore((state) => state.workloadType);
  const topK = useUiStore((state) => state.topK);
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);
  // The map mirrors SearchPanel's ranked list; sharing params via the store
  // keeps both views in sync without prop drilling or duplicate fetches.
  const query = useSearchSites({
    power_mw: powerMw,
    workload_type: workloadType,
    top_k: topK
  });
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
