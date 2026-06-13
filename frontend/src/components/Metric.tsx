interface MetricProps {
  label: string;
  value: string;
}

export function Metric({ label, value }: MetricProps) {
  return (
    <div className="rounded-lg border border-subtle px-3 py-2">
      <span className="block text-[0.6875rem] lowercase tracking-wide text-dim">
        {label}
      </span>
      <span className="break-words text-sm text-primary">{value}</span>
    </div>
  );
}
