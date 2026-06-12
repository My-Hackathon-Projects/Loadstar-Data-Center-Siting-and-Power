import { describe, expect, it } from "vitest";

import {
  formatCarbon,
  formatDistanceKm,
  formatEurPerMwh,
  formatMw,
  formatPercent
} from "./formatters";

describe("formatters", () => {
  it("formats energy planning units for the demo UI", () => {
    expect(formatMw(280)).toBe("280 MW");
    expect(formatEurPerMwh(34.2)).toBe("34 EUR/MWh");
    expect(formatCarbon(24.4)).toBe("24 gCO2/kWh");
    expect(formatDistanceKm(18.44)).toBe("18.4 km");
    expect(formatPercent(0.847)).toBe("85%");
  });
});
