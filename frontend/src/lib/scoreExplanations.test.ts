import { describe, expect, it } from "vitest";

import { scoreFactorLabel, topScoreExplanations } from "./scoreExplanations";

describe("scoreExplanations", () => {
  it("labels and orders score drivers by weighted contribution", () => {
    const explanations = [
      {
        factor: "carbon",
        score: 0.9,
        weight: 0.24,
        contribution: 0.216,
        raw_value: "24 gCO2/kWh",
        direction: "lower_is_better" as const,
      },
      {
        factor: "price",
        score: 0.6,
        weight: 0.18,
        contribution: 0.108,
        raw_value: "34 EUR/MWh",
        direction: "lower_is_better" as const,
      },
      {
        factor: "grid",
        score: 0,
        weight: 0.14,
        contribution: 0,
        raw_value: "7.2 km",
        direction: "lower_is_better" as const,
      },
    ];

    expect(scoreFactorLabel("ml")).toBe("ML viability");
    expect(
      topScoreExplanations(explanations, 2).map((item) => item.factor),
    ).toEqual(["carbon", "price"]);
  });
});
