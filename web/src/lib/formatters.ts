const numberFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0
});

const oneDecimalFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 1
});

export function formatMw(value: number): string {
  return `${numberFormatter.format(value)} MW`;
}

export function formatCarbon(value: number): string {
  return `${numberFormatter.format(value)} gCO2/kWh`;
}

export function formatEurPerMwh(value: number): string {
  return `${numberFormatter.format(value)} EUR/MWh`;
}

export function formatPercent(value: number): string {
  return `${numberFormatter.format(value * 100)}%`;
}

export function formatDistanceKm(value: number): string {
  return `${oneDecimalFormatter.format(value)} km`;
}
