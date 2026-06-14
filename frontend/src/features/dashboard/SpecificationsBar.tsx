import {
  COUNTRY_FILTER_OPTIONS,
  SEARCH_TOP_K_OPTIONS,
  WEIGHT_FACTORS,
  WORKLOAD_TYPE_OPTIONS,
} from "../../config/defaults";
import { useSearchRequest } from "../../hooks/useSearchRequest";
import { useUiStore } from "../../hooks/useUiStore";
import { useSearchSites } from "../../lib/queries";
import type { SearchRequest } from "../../types/api";
import { LayerControls } from "../map/LayerControls";
import { RankedSites } from "../search/RankedSites";

interface SpecificationsBarProps {
  open: boolean;
  onToggle: () => void;
}

export function SpecificationsBar({ open, onToggle }: SpecificationsBarProps) {
  const powerMw = useUiStore((state) => state.powerMw);
  const workloadType = useUiStore((state) => state.workloadType);
  const topK = useUiStore((state) => state.topK);
  const weights = useUiStore((state) => state.weights);
  const countryFilter = useUiStore((state) => state.countryFilter);
  const setSearchParams = useUiStore((state) => state.setSearchParams);
  const setWeight = useUiStore((state) => state.setWeight);
  const toggleCountryFilter = useUiStore((state) => state.toggleCountryFilter);
  const query = useSearchSites(useSearchRequest());

  if (!open) {
    return (
      <aside className="flex flex-col items-center rounded-2xl border border-subtle bg-panel py-3 lg:h-full">
        <button
          aria-label="Expand specifications"
          className="text-dim transition-colors hover:text-primary"
          onClick={onToggle}
          type="button"
        >
          ›
        </button>
        <span className="mt-3 [writing-mode:vertical-rl] text-[0.6875rem] lowercase tracking-[0.2em] text-dim">
          specifications
        </span>
      </aside>
    );
  }

  return (
    <aside className="flex flex-col rounded-2xl border border-subtle bg-panel p-4 lg:h-full lg:overflow-y-auto">
      <div className="flex items-center justify-between">
        <p className="eyebrow">specifications</p>
        <button
          aria-label="Collapse specifications"
          className="text-dim transition-colors hover:text-primary"
          onClick={onToggle}
          type="button"
        >
          ‹
        </button>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3">
        <label className="grid gap-1 text-xs lowercase tracking-wide text-dim">
          mw
          <input
            className="rounded-md border border-subtle bg-void px-3 py-2 text-sm text-primary outline-none focus:border-accent"
            min={1}
            onChange={(event) =>
              setSearchParams({
                powerMw: Math.max(1, Number(event.target.value) || 1),
              })
            }
            type="number"
            value={powerMw}
          />
        </label>
        <label className="grid gap-1 text-xs lowercase tracking-wide text-dim">
          results
          <select
            className="rounded-md border border-subtle bg-void px-3 py-2 text-sm text-primary outline-none focus:border-accent"
            onChange={(event) =>
              setSearchParams({ topK: Number(event.target.value) })
            }
            value={topK}
          >
            {SEARCH_TOP_K_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="col-span-2 grid gap-1 text-xs lowercase tracking-wide text-dim">
          workload
          <select
            className="rounded-md border border-subtle bg-void px-3 py-2 text-sm text-primary outline-none focus:border-accent"
            onChange={(event) =>
              setSearchParams({
                workloadType: event.target
                  .value as SearchRequest["workload_type"],
              })
            }
            value={workloadType}
          >
            {WORKLOAD_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-4">
        <p className="eyebrow">weights</p>
        <div className="mt-2 grid gap-2">
          {WEIGHT_FACTORS.map((factor) => (
            <label
              className="grid grid-cols-[1fr_auto] items-center gap-2 text-xs text-dim"
              key={factor.key}
            >
              <span className="lowercase">{factor.label}</span>
              <span className="tabular-nums text-primary">
                {weights[factor.key].toFixed(2)}
              </span>
              <input
                className="col-span-2 accent-accent"
                max={0.4}
                min={0}
                onChange={(event) =>
                  setWeight(factor.key, Number(event.target.value))
                }
                step={0.01}
                type="range"
                value={weights[factor.key]}
              />
            </label>
          ))}
        </div>
      </div>

      <div className="mt-4">
        <p className="eyebrow">map layer</p>
        <div className="mt-2">
          <LayerControls />
        </div>
      </div>

      <div className="mt-4">
        <p className="eyebrow">filters</p>
        <div className="mt-2 flex max-h-44 flex-wrap gap-1.5 overflow-y-auto pr-1">
          {COUNTRY_FILTER_OPTIONS.map((option) => {
            const active = countryFilter.includes(option.code);
            return (
              <button
                className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                  active
                    ? "border-accent bg-accent text-accent-contrast"
                    : "border-subtle text-dim hover:border-strong hover:text-primary"
                }`}
                key={option.code}
                onClick={() => toggleCountryFilter(option.code)}
                type="button"
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-4">
        <p className="eyebrow">ranked sites</p>
        {query.isError ? (
          <p className="mt-2 rounded-lg border border-danger p-3 text-sm text-danger">
            {query.error.message}
          </p>
        ) : null}
        {query.data?.warnings.map((warning) => (
          <p
            className="mt-2 rounded-lg border border-warning p-2 text-xs text-warning"
            key={warning.code}
          >
            {warning.message}
          </p>
        ))}
        <RankedSites
          isLoading={query.isLoading}
          results={query.data?.results ?? []}
        />
      </div>
    </aside>
  );
}
