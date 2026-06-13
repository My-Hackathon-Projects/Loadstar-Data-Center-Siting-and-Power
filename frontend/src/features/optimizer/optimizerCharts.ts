import type { DispatchPreviewRow } from "../../types/api";

export interface DispatchChartRow {
  backup: number;
  battery: number;
  clean: number;
  grid: number;
  hour: number;
  load: number;
}

export function dispatchChartRows(
  rows: DispatchPreviewRow[],
): DispatchChartRow[] {
  return rows.map((row) => ({
    backup: numberValue(row.backup_mw),
    battery:
      numberValue(row.battery_discharge_mw) -
      numberValue(row.battery_charge_mw),
    clean:
      numberValue(row.wind_ppa_mw) +
      numberValue(row.solar_ppa_mw) +
      numberValue(row.onsite_solar_mw),
    grid: numberValue(row.grid_mw),
    hour: numberValue(row.hour),
    load: numberValue(row.load_mw),
  }));
}

function numberValue(value: number | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
