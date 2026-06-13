export interface PortfolioRow {
  key: string;
  label: string;
  value: number;
}

export function portfolioRows(portfolio: Record<string, number>): PortfolioRow[] {
  return Object.entries(portfolio).map(([key, value]) => ({
    key,
    label: formatPortfolioKey(key),
    value,
  }));
}

export function summaryMetric(summary: Record<string, number>, key: string): number {
  return summary[key] ?? 0;
}

export function formatPortfolioKey(key: string): string {
  return key.replaceAll("_", " ");
}
