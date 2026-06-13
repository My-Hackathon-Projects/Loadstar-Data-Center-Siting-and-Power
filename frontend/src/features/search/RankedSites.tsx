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
  const comparisonCellIds = useUiStore((state) => state.comparisonCellIds);
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);
  const toggleComparisonCell = useUiStore(
    (state) => state.toggleComparisonCell,
  );
  if (isLoading) {
    return <p className="mt-3 text-sm text-dim">Loading ranked cells...</p>;
  }
  if (results.length === 0) {
    return (
      <p className="mt-3 rounded-lg border border-subtle p-3 text-sm text-dim">
        No cells pass exclusions and headroom for this request.
      </p>
    );
  }
  return (
    <div className="mt-3 grid gap-2">
      {results.map((result, index) => {
        const isSelected = selectedCellId === result.site.cell_id;
        const isCompared = comparisonCellIds.includes(result.site.cell_id);
        const drivers = topScoreExplanations(result.score_explanations, 3)
          .map(
            (driver) =>
              `${scoreFactorLabel(driver.factor)} ${formatPercent(driver.contribution)}`,
          )
          .join(" · ");

        return (
          <div
            className={`rounded-lg border p-3 transition-colors ${
              isSelected
                ? "border-accent bg-panel-raised"
                : "border-subtle hover:border-strong"
            }`}
            key={result.site.cell_id}
          >
            <span className="flex items-start justify-between gap-3">
              <button
                className="min-w-0 flex-1 text-left"
                type="button"
                onClick={() => setSelectedCellId(result.site.cell_id)}
              >
                <strong className="block text-sm text-primary">
                  {index + 1}. {result.site.region_name}
                </strong>
                <span className="text-xs text-dim">
                  Score {formatPercent(result.composite_score)} ·{" "}
                  {formatMw(result.site.headroom_mw)} headroom ·{" "}
                  {formatCarbon(result.site.carbon_intensity_g_kwh)}
                </span>
              </button>
              <button
                className={`rounded-md border px-2 py-1 text-xs transition-colors ${
                  isCompared
                    ? "border-accent bg-accent text-accent-contrast"
                    : "border-subtle text-dim hover:border-strong hover:text-primary"
                }`}
                type="button"
                onClick={() => toggleComparisonCell(result.site.cell_id)}
              >
                {isCompared ? "Compared" : "Compare"}
              </button>
            </span>
            {drivers ? (
              <span className="mt-1 block text-xs text-faint">
                Drivers: {drivers}
              </span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
