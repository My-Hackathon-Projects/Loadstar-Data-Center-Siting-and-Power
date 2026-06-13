import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ParetoPoint } from "../../types/api";
import type { DispatchChartRow } from "./optimizerCharts";

interface ParetoChartProps {
  points: ParetoPoint[];
}

export function ParetoChart({ points }: ParetoChartProps) {
  return (
    <div className="mt-3 h-56 rounded-md border border-slate-200 p-2">
      <ResponsiveContainer height="100%" width="100%">
        <LineChart
          data={points}
          margin={{ bottom: 16, left: 8, right: 18, top: 12 }}
        >
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" />
          <XAxis
            dataKey="effective_carbon_g_kwh"
            label={{ position: "insideBottom", value: "Carbon gCO2/kWh" }}
            tick={{ fontSize: 12 }}
          />
          <YAxis
            dataKey="effective_cost_eur_mwh"
            label={{ angle: -90, position: "insideLeft", value: "EUR/MWh" }}
            tick={{ fontSize: 12 }}
            width={52}
          />
          <Tooltip />
          <Line
            dataKey="effective_cost_eur_mwh"
            dot={{ r: 3 }}
            name="Cost"
            stroke="#0e7490"
            strokeWidth={3}
            type="monotone"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

interface DispatchChartProps {
  rows: DispatchChartRow[];
}

export function DispatchChart({ rows }: DispatchChartProps) {
  return (
    <div className="mt-3 h-56 rounded-md border border-slate-200 p-2">
      <ResponsiveContainer height="100%" width="100%">
        <LineChart
          data={rows}
          margin={{ bottom: 16, left: 8, right: 18, top: 12 }}
        >
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" />
          <XAxis
            dataKey="hour"
            label={{ position: "insideBottom", value: "Hour" }}
            tick={{ fontSize: 12 }}
          />
          <YAxis tick={{ fontSize: 12 }} width={52} />
          <Tooltip />
          <Legend verticalAlign="top" />
          <Line
            dataKey="load"
            dot={false}
            name="Load"
            stroke="#111827"
            strokeWidth={2}
          />
          <Line
            dataKey="grid"
            dot={false}
            name="Grid"
            stroke="#64748b"
            strokeWidth={2}
          />
          <Line
            dataKey="clean"
            dot={false}
            name="Clean"
            stroke="#15803d"
            strokeWidth={2}
          />
          <Line
            dataKey="battery"
            dot={false}
            name="Battery"
            stroke="#c2410c"
            strokeWidth={2}
          />
          <Line
            dataKey="backup"
            dot={false}
            name="Backup"
            stroke="#be123c"
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
