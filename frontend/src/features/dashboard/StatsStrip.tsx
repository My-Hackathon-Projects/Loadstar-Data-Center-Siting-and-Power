import { useSearchRequest } from "../../hooks/useSearchRequest";
import { useUiStore } from "../../hooks/useUiStore";
import { useSearchSites, useSupplyMix } from "../../lib/queries";
import { buildStatCards, type StatTone } from "./statCards";

const TONE_CLASS: Record<StatTone, string> = {
  neutral: "text-dim",
  positive: "text-positive",
  warning: "text-warning",
};

export function StatsStrip() {
  const search = useSearchSites(useSearchRequest());
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const powerMw = useUiStore((state) => state.powerMw);
  const loadProfile = useUiStore((state) => state.loadProfile);
  const supplyMix = useSupplyMix(selectedCellId, powerMw, loadProfile);
  const cards = buildStatCards(search.data?.results ?? [], supplyMix.data);

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
      {cards.map((card) => (
        <div
          className="rounded-xl border border-subtle bg-panel px-3 py-2.5"
          key={card.key}
        >
          <p className="eyebrow">{card.label}</p>
          <p className="mt-1 text-xl font-light tabular-nums text-primary">
            {card.value}
          </p>
          <p
            className={`mt-0.5 text-xs ${
              card.delta ? TONE_CLASS[card.delta.tone] : "text-faint"
            }`}
          >
            {card.delta ? card.delta.text : " "}
          </p>
        </div>
      ))}
    </div>
  );
}
