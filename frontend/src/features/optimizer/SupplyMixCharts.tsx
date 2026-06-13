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

import { CHART_SERIES, COLOR } from "../../styles/tokens";
import type { ParetoPoint } from "../../types/api";
import type { DispatchChartRow } from "./optimizerCharts";

const AXIS_TICK = { fontSize: 12, fill: COLOR.textDim } as const;
const TOOLTIP_CONTENT = {
  background: COLOR.bgPanel,
  border: `1px solid ${COLOR.borderSubtle}`,
  borderRadius: 8,
  color: COLOR.textPrimary,
} as const;
const LEGEND_STYLE = { color: COLOR.textDim, fontSize: 12 } as const;

interface ParetoChartProps {
  points: ParetoPoint[];
}

export function ParetoChart({ points }: ParetoChartProps) {
  return (
    <div className="mt-3 h-56 rounded-lg border border-subtle p-2">
      <ResponsiveContainer height="100%" width="100%">
        <LineChart
          data={points}
          margin={{ bottom: 16, left: 8, right: 18, top: 12 }}
        >
          <CartesianGrid stroke={COLOR.borderSubtle} strokeDasharray="4 4" />
          <XAxis
            dataKey="effective_carbon_g_kwh"
            label={{
              fill: COLOR.textDim,
              position: "insideBottom",
              value: "Carbon gCO2/kWh",
            }}
            stroke={COLOR.textDim}
            tick={AXIS_TICK}
          />
          <YAxis
            dataKey="effective_cost_eur_mwh"
            label={{
              angle: -90,
              fill: COLOR.textDim,
              position: "insideLeft",
              value: "EUR/MWh",
            }}
            stroke={COLOR.textDim}
            tick={AXIS_TICK}
            width={52}
          />
          <Tooltip contentStyle={TOOLTIP_CONTENT} />
          <Line
            dataKey="effective_cost_eur_mwh"
            dot={{ fill: COLOR.accent, r: 3 }}
            name="Cost"
            stroke={COLOR.accent}
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
    <div className="mt-3 h-56 rounded-lg border border-subtle p-2">
      <ResponsiveContainer height="100%" width="100%">
        <LineChart
          data={rows}
          margin={{ bottom: 16, left: 8, right: 18, top: 12 }}
        >
          <CartesianGrid stroke={COLOR.borderSubtle} strokeDasharray="4 4" />
          <XAxis
            dataKey="hour"
            label={{
              fill: COLOR.textDim,
              position: "insideBottom",
              value: "Hour",
            }}
            stroke={COLOR.textDim}
            tick={AXIS_TICK}
          />
          <YAxis stroke={COLOR.textDim} tick={AXIS_TICK} width={52} />
          <Tooltip contentStyle={TOOLTIP_CONTENT} />
          <Legend verticalAlign="top" wrapperStyle={LEGEND_STYLE} />
          <Line
            dataKey="load"
            dot={false}
            name="Load"
            stroke={CHART_SERIES.load}
            strokeWidth={2}
          />
          <Line
            dataKey="grid"
            dot={false}
            name="Grid"
            stroke={CHART_SERIES.grid}
            strokeWidth={2}
          />
          <Line
            dataKey="clean"
            dot={false}
            name="Clean"
            stroke={CHART_SERIES.clean}
            strokeWidth={2}
          />
          <Line
            dataKey="battery"
            dot={false}
            name="Battery"
            stroke={CHART_SERIES.battery}
            strokeWidth={2}
          />
          <Line
            dataKey="backup"
            dot={false}
            name="Backup"
            stroke={CHART_SERIES.backup}
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
