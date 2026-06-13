import type { ScoreExplanation } from "../types/api";

const FACTOR_LABELS: Record<string, string> = {
  price: "Price",
  carbon: "Carbon",
  congestion: "Congestion",
  grid: "Grid",
  connectivity: "Connectivity",
  land: "Land",
  ml: "ML viability",
};

export function scoreFactorLabel(factor: string): string {
  return FACTOR_LABELS[factor] ?? factor;
}

export function topScoreExplanations(
  explanations: ScoreExplanation[],
  limit: number,
): ScoreExplanation[] {
  return [...explanations]
    .filter((explanation) => explanation.contribution > 0)
    .sort(
      (left, right) =>
        right.contribution - left.contribution ||
        left.factor.localeCompare(right.factor),
    )
    .slice(0, limit);
}
