import {
  formatCarbon,
  formatEurPerMwh,
  formatMw,
  formatPercent,
} from "../../lib/formatters";
import type { RankedSite, SupplyMixResponse } from "../../types/api";

export type StatTone = "neutral" | "positive" | "warning";

export interface StatDelta {
  text: string;
  tone: StatTone;
}

export interface StatCard {
  key: string;
  label: string;
  /** Prominent formatted value, or the placeholder dash when not yet available. */
  value: string;
  delta?: StatDelta;
}

/** Muted dash for cards whose data is not available yet (no selection / no optimizer run). */
export const STAT_PLACEHOLDER = "—";

function mean(values: number[]): number {
  if (values.length === 0) {
    return 0;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

/**
 * A "vs field" delta: how the top site compares to the mean of all candidates on
 * one raw field. `higherBetter` decides whether being above the mean is positive
 * (green) or a warning (amber).
 */
function fieldDelta(
  value: number,
  field: number[],
  higherBetter: boolean,
  format: (delta: number) => string,
): StatDelta | undefined {
  if (field.length < 2) {
    return undefined;
  }
  const diff = value - mean(field);
  const rounded = Math.round(diff * 100) / 100;
  const sign = rounded > 0 ? "+" : "";
  const isGood = higherBetter ? rounded >= 0 : rounded <= 0;
  return {
    text: `${sign}${format(rounded)} vs field`,
    tone: isGood ? "positive" : "warning",
  };
}

/**
 * The seven dashboard stat cards. Five come from the search results; effective
 * cost and CFE share come from the auto-run optimizer and show a placeholder
 * until it resolves for the selected cell.
 */
export function buildStatCards(
  results: RankedSite[],
  supplyMix: SupplyMixResponse | undefined,
): StatCard[] {
  const top = results[0];
  const scores = results.map((result) => result.composite_score);
  const prices = results.map((result) => result.site.mean_price_eur_mwh);
  const carbons = results.map((result) => result.site.carbon_intensity_g_kwh);
  const headrooms = results.map((result) => result.site.headroom_mw);

  return [
    {
      key: "candidates",
      label: "candidates",
      value: String(results.length),
    },
    {
      key: "top-score",
      label: "top site score",
      value: top ? formatPercent(top.composite_score) : STAT_PLACEHOLDER,
      delta: top
        ? fieldDelta(
            top.composite_score,
            scores,
            true,
            (delta) => `${Math.round(delta * 100)} pts`,
          )
        : undefined,
    },
    {
      key: "price",
      label: "price eur/mwh",
      value: top ? formatEurPerMwh(top.site.mean_price_eur_mwh) : STAT_PLACEHOLDER,
      delta: top
        ? fieldDelta(
            top.site.mean_price_eur_mwh,
            prices,
            false,
            (delta) => `${Math.round(delta)}`,
          )
        : undefined,
    },
    {
      key: "carbon",
      label: "carbon gco2/kwh",
      value: top
        ? formatCarbon(top.site.carbon_intensity_g_kwh)
        : STAT_PLACEHOLDER,
      delta: top
        ? fieldDelta(
            top.site.carbon_intensity_g_kwh,
            carbons,
            false,
            (delta) => `${Math.round(delta)}`,
          )
        : undefined,
    },
    {
      key: "headroom",
      label: "headroom mw",
      value: top ? formatMw(top.site.headroom_mw) : STAT_PLACEHOLDER,
      delta: top
        ? fieldDelta(
            top.site.headroom_mw,
            headrooms,
            true,
            (delta) => `${Math.round(delta)}`,
          )
        : undefined,
    },
    {
      key: "effective-cost",
      label: "effective cost",
      value: supplyMix
        ? formatEurPerMwh(supplyMix.effective_cost_eur_mwh)
        : STAT_PLACEHOLDER,
    },
    {
      key: "cfe-share",
      label: "24/7 cfe share",
      value: supplyMix
        ? formatPercent(supplyMix.hourly_24_7_cfe_share)
        : STAT_PLACEHOLDER,
      delta: supplyMix
        ? {
            text: supplyMix.hourly_24_7_cfe_share >= 0.9 ? "carbon-free" : "below 24/7",
            tone: supplyMix.hourly_24_7_cfe_share >= 0.9 ? "positive" : "warning",
          }
        : undefined,
    },
  ];
}
