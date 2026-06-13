export interface TechSource {
  name: string;
  role: string;
}

export interface TechSection {
  number: string;
  eyebrow: string;
  title: string;
  body: string[];
  sources?: TechSource[];
}

/**
 * Static narrative for the Behind the Tech page. No API dependency — this is the
 * story of how Loadstar works, told in the same quiet dark language as the rest
 * of the product.
 */
export const TECH_SECTIONS: TechSection[] = [
  {
    number: "01",
    eyebrow: "the data",
    title: "Every cell is grounded in official records.",
    body: [
      "Europe is divided into H3 cells. Each one is enriched from public, citable sources so a recommendation can always be traced back to a number someone can check.",
    ],
    sources: [
      { name: "ENTSO-E Transparency", role: "day-ahead electricity prices and grid load" },
      { name: "Ember", role: "hourly grid carbon intensity" },
      { name: "Copernicus ERA5", role: "wind and solar capacity factors, cooling demand" },
      { name: "Google DeepMind AlphaEarth", role: "satellite embeddings for land suitability" },
      { name: "OpenStreetMap and Natural Earth", role: "boundaries, exclusions, buildable land" },
      { name: "Submarine cable and IXP maps", role: "fiber and interconnect distance" },
    ],
  },
  {
    number: "02",
    eyebrow: "the models",
    title: "Embeddings find the land. A gradient-boosted model judges it.",
    body: [
      "AlphaEarth embeddings feed a suitability classifier that learns what built data-center land looks like from orbit, scoring every cell on similarity to real sites.",
      "A LightGBM siting model then ranks viability across the full feature set. SHAP values come back with every prediction, so the dashboard can name the exact drivers behind a score instead of asking you to trust a black box.",
    ],
  },
  {
    number: "03",
    eyebrow: "the optimizer",
    title: "A linear program builds the cheapest clean supply mix.",
    body: [
      "For a selected cell the optimizer solves an hourly dispatch over grid, wind and solar PPAs, on-site solar, batteries, and backup, minimizing effective cost under a carbon cap.",
      "Sweeping the cap traces a Pareto frontier of cost against carbon, and the 24/7 CFE metric reports how much of the load is matched by carbon-free energy hour by hour, not just on annual average.",
    ],
  },
  {
    number: "04",
    eyebrow: "the agent",
    title: "Fred runs the real search and never invents a number.",
    body: [
      "A free-text request is parsed into a real search over the same engine the dashboard uses. Fred adjusts the weights, applies filters, and flies the map to the result.",
      "When a language model is configured it only narrates the answer around the engine's numbers; the figures themselves always come from the search and the optimizer. With no key, a deterministic path produces the same grounded result, so a live demo never breaks.",
    ],
  },
  {
    number: "05",
    eyebrow: "the architecture",
    title: "One pipeline, from public data to a cinematic console.",
    body: [
      "Data is ingested and engineered offline, the engine scores and optimizes in pure Python, a FastAPI service exposes typed contracts, and a React console renders the map, the charts, and Fred.",
    ],
  },
];
