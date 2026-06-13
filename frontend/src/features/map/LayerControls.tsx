import { useUiStore } from "../../hooks/useUiStore";
import { MAP_LAYER_OPTIONS } from "./mapLayers";

export function LayerControls() {
  const activeLayer = useUiStore((state) => state.activeLayer);
  const setActiveLayer = useUiStore((state) => state.setActiveLayer);

  return (
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
  );
}
