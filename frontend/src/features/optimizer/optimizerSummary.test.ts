import { describe, expect, it } from "vitest";

import {
  formatPortfolioKey,
  portfolioRows,
  summaryMetric,
} from "./optimizerSummary";

describe("optimizer summary helpers", () => {
  it("formats portfolio rows for display", () => {
    expect(
      portfolioRows({
        grid: 0.4,
        wind_ppa: 0.6,
      }),
    ).toEqual([
      { key: "grid", label: "grid", value: 0.4 },
      { key: "wind_ppa", label: "wind ppa", value: 0.6 },
    ]);
  });

  it("reads optional summary metrics with a zero fallback", () => {
    expect(summaryMetric({ battery_power_capacity_mw: 12 }, "battery_power_capacity_mw")).toBe(12);
    expect(summaryMetric({}, "battery_energy_capacity_mwh")).toBe(0);
    expect(formatPortfolioKey("onsite_solar")).toBe("onsite solar");
  });
});
