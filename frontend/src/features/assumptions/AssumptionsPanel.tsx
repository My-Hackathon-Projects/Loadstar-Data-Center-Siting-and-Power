import { useAssumptions } from "../../lib/queries";

const IMPORTANT_OPTIMIZER_KEYS = [
  "wind_ppa_eur_mwh",
  "solar_ppa_eur_mwh",
  "battery_capex_eur_kwh",
  "frontier_points",
] as const;

export function AssumptionsPanel() {
  const query = useAssumptions();
  const assumptions = query.data?.assumptions;
  const weights = recordValue(assumptions, "scoring_weights");
  const optimizer = recordValue(assumptions, "optimizer");

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Assumptions</h2>
          <p className="mt-1 text-sm text-slate-600">
            {query.data?.data_mode ?? "fixture"} data mode
          </p>
        </div>
        {query.data?.cache_key ? (
          <span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-500">
            Cached
          </span>
        ) : null}
      </div>
      {query.isError ? (
        <p className="mt-3 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">
          Assumptions could not be loaded.
        </p>
      ) : null}
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
        <AssumptionList title="Scoring Weights" values={weights} />
        <AssumptionList
          keys={IMPORTANT_OPTIMIZER_KEYS}
          title="Optimizer Inputs"
          values={optimizer}
        />
      </div>
    </section>
  );
}

interface AssumptionListProps {
  keys?: readonly string[];
  title: string;
  values: Record<string, unknown> | null;
}

function AssumptionList({ keys, title, values }: AssumptionListProps) {
  const entries = values
    ? Object.entries(values).filter(([key]) => !keys || keys.includes(key))
    : [];

  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      <dl className="mt-2 grid gap-2">
        {entries.map(([key, value]) => (
          <div
            className="flex items-center justify-between gap-3 rounded-md border border-slate-200 px-3 py-2 text-sm"
            key={key}
          >
            <dt className="break-words text-slate-600">
              {key.replaceAll("_", " ")}
            </dt>
            <dd className="shrink-0 font-medium text-slate-900">
              {formatUnknown(value)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function recordValue(
  values: Record<string, unknown> | undefined,
  key: string,
): Record<string, unknown> | null {
  const value = values?.[key];
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function formatUnknown(value: unknown): string {
  if (typeof value === "number") {
    return value < 1
      ? value.toFixed(2)
      : Math.round(value).toLocaleString("en-US");
  }
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  return "n/a";
}
