interface MetricProps {
  label: string;
  value: string;
}

export function Metric({ label, value }: MetricProps) {
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <span className="block text-xs text-slate-500">{label}</span>
      <span className="break-words text-sm text-slate-900">{value}</span>
    </div>
  );
}
