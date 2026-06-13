import { useUiStore } from "../../hooks/useUiStore";
import { MAP_LAYER_OPTIONS } from "./mapLayers";

export function LayerControls() {
  const activeLayer = useUiStore((state) => state.activeLayer);
  const setActiveLayer = useUiStore((state) => state.setActiveLayer);

  return (
    <div className="flex flex-wrap gap-2">
      {MAP_LAYER_OPTIONS.map((option) => (
        <button
          className={`rounded border px-3 py-1.5 text-xs font-medium ${
            activeLayer === option.name
              ? "border-cyan-700 bg-cyan-700 text-white"
              : "border-slate-300 bg-white text-slate-700 hover:border-cyan-700"
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
