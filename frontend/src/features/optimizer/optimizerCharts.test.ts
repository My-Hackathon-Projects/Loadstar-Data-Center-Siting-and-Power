import { describe, expect, it } from "vitest";

import { dispatchChartRows } from "./optimizerCharts";

describe("optimizer chart helpers", () => {
  it("maps API dispatch rows into chart-ready load, clean, grid, and battery series", () => {
    expect(
      dispatchChartRows([
        {
          backup_mw: 1,
          battery_charge_mw: 2,
          battery_discharge_mw: 5,
          grid_mw: 120,
          hour: 7,
          load_mw: 280,
          onsite_solar_mw: 30,
          solar_ppa_mw: 20,
          wind_ppa_mw: 60,
        },
      ]),
    ).toEqual([
      {
        backup: 1,
        battery: 3,
        clean: 110,
        grid: 120,
        hour: 7,
        load: 280,
      },
    ]);
  });
});
