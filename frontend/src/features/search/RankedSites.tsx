import type { RankedSite } from "../../types/api";
import { useUiStore } from "../../hooks/useUiStore";
import { formatCarbon, formatMw, formatPercent } from "../../lib/formatters";
import {
  scoreFactorLabel,
  topScoreExplanations,
} from "../../lib/scoreExplanations";

interface RankedSitesProps {
  isLoading: boolean;
  results: RankedSite[];
}

export function RankedSites({ isLoading, results }: RankedSitesProps) {
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);
  if (isLoading) {
    return (
      <p className="mt-4 text-sm text-slate-500">Loading fixture sites...</p>
    );
  }
  return (
    <div className="mt-4 grid gap-2">
      {results.map((result, index) => {
        const drivers = topScoreExplanations(result.score_explanations, 3)
          .map(
            (driver) =>
              `${scoreFactorLabel(driver.factor)} ${formatPercent(driver.contribution)}`,
          )
          .join(" · ");

        return (
          <button
            className="rounded-md border border-slate-200 bg-slate-50 p-3 text-left hover:border-cyan-700"
            key={result.site.cell_id}
            type="button"
            onClick={() => setSelectedCellId(result.site.cell_id)}
          >
            <strong className="block text-sm">
              {index + 1}. {result.site.region_name}
            </strong>
            <span className="text-xs text-slate-600">
              Score {result.composite_score} ·{" "}
              {formatMw(result.site.headroom_mw)} headroom ·{" "}
              {formatCarbon(result.site.carbon_intensity_g_kwh)}
            </span>
            {drivers ? (
              <span className="mt-1 block text-xs text-slate-500">
                Drivers: {drivers}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
