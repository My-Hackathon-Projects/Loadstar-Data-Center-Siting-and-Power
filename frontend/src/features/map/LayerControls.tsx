import type { GridMode } from "../../hooks/useUiStore";
import { useUiStore } from "../../hooks/useUiStore";
import { MAP_LAYER_OPTIONS } from "./mapLayers";

const GRID_MODES: ReadonlyArray<{ key: GridMode; label: string; title: string }> = [
  { key: "auto", label: "Auto", title: "Voltage tiers shown depend on zoom" },
  { key: "backbone", label: "Backbone", title: "Show only the >= 380 kV backbone" },
  { key: "all", label: "All HV", title: "Show every line >= 220 kV" },
];

export function LayerControls() {
  const activeLayer = useUiStore((state) => state.activeLayer);
  const setActiveLayer = useUiStore((state) => state.setActiveLayer);
  const showGrid = useUiStore((state) => state.showGrid);
  const setShowGrid = useUiStore((state) => state.setShowGrid);
  const gridMode = useUiStore((state) => state.gridMode);
  const setGridMode = useUiStore((state) => state.setGridMode);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1.5">
        {MAP_LAYER_OPTIONS.map((option) => (
          <button
            className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
              activeLayer === option.name
                ? "border-accent bg-accent text-accent-contrast"
                : "border-subtle text-dim hover:border-strong hover:text-primary"
            }`}
            key={option.name}
            title={option.label}
            type="button"
            onClick={() => setActiveLayer(option.name)}
          >
            {option.shortLabel}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-subtle pt-2">
        <span className="eyebrow text-[10px] text-dim">overlays</span>
        <button
          aria-pressed={showGrid}
          className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
            showGrid
              ? "border-strong text-primary"
              : "border-subtle text-dim hover:border-strong hover:text-primary"
          }`}
          title="Toggle the PyPSA-Eur HV transmission grid overlay"
          type="button"
          onClick={() => setShowGrid(!showGrid)}
        >
          Grid
        </button>
        {showGrid ? (
          <div
            className="flex gap-0.5 rounded-md border border-subtle p-0.5 text-[10px] text-dim"
            role="radiogroup"
            aria-label="Grid voltage filter"
          >
            {GRID_MODES.map((mode) => (
              <button
                aria-checked={gridMode === mode.key}
                className={`rounded px-1.5 py-0.5 transition-colors ${
                  gridMode === mode.key
                    ? "bg-panel-raised text-primary"
                    : "hover:text-primary"
                }`}
                key={mode.key}
                role="radio"
                title={mode.title}
                type="button"
                onClick={() => setGridMode(mode.key)}
              >
                {mode.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
