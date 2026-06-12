const numberFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0
});

const oneDecimalFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 1
});

/** Format a load size in megawatts (no decimals). Example: `formatMw(280) === "280 MW"`. */
export function formatMw(value: number): string {
  return `${numberFormatter.format(value)} MW`;
}

/** Format a carbon-intensity value in gCO2/kWh (no decimals). */
export function formatCarbon(value: number): string {
  return `${numberFormatter.format(value)} gCO2/kWh`;
}

/** Format a price per MWh in euros (no decimals). */
export function formatEurPerMwh(value: number): string {
  return `${numberFormatter.format(value)} EUR/MWh`;
}

/** Format a 0..1 ratio as a whole-number percentage. `formatPercent(0.85) === "85%"`. */
export function formatPercent(value: number): string {
  return `${numberFormatter.format(value * 100)}%`;
}

/** Format a distance in kilometres with one decimal place. */
export function formatDistanceKm(value: number): string {
  return `${oneDecimalFormatter.format(value)} km`;
}
