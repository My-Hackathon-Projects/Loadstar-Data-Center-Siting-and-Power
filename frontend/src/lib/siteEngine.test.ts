import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  compareSitesLocal,
  getSiteLocal,
  rankSites,
  searchSitesLocal,
  type SearchInput,
} from "./siteEngine";
import { DEFAULT_WEIGHTS } from "../config/defaults";
import type { LayerResponse, SiteFeature } from "../types/api";

const HERE = dirname(fileURLToPath(import.meta.url));
const PUBLIC = resolve(HERE, "../../public");

const sites = JSON.parse(
  readFileSync(resolve(PUBLIC, "data/sites.json"), "utf-8"),
) as SiteFeature[];

const compositeLayer = JSON.parse(
  readFileSync(resolve(PUBLIC, "layers/composite_score.json"), "utf-8"),
) as LayerResponse;

describe("siteEngine parity with the backend", () => {
  it("re-derives the composite-score layer the backend generated", () => {
    // The layer is produced by the Python engine (rank_sites at power_mw=1,
    // default weights). The client engine must reproduce it cell-for-cell, or
    // search results on the deployed SPA would diverge from local/API.
    const request: SearchInput = { power_mw: 1, weights: DEFAULT_WEIGHTS, top_k: sites.length };
    const ranked = rankSites(request, sites);
    const byCell = new Map(ranked.map((result) => [result.site.cell_id, result.composite_score]));

    expect(ranked.length).toBe(sites.length);
    for (const feature of compositeLayer.features) {
      const local = byCell.get(feature.properties.cell_id);
      expect(local).toBeDefined();
      // 4-decimal rounding on both sides; allow one rounding ULP of slack.
      expect(Math.abs((local ?? 0) - feature.properties.layer_value)).toBeLessThan(1e-3);
    }
  });
});

describe("siteEngine behavior", () => {
  it("filters out cells below the requested headroom", () => {
    const power = 280;
    const response = searchSitesLocal({ power_mw: power, top_k: 100 }, sites);
    expect(response.results.length).toBeGreaterThan(0);
    for (const result of response.results) {
      expect(result.site.headroom_mw).toBeGreaterThanOrEqual(power);
    }
  });

  it("ranks best-first and honors top_k", () => {
    const response = searchSitesLocal({ power_mw: 1, top_k: 5 }, sites);
    expect(response.results).toHaveLength(5);
    const scores = response.results.map((r) => r.composite_score);
    expect(scores).toEqual([...scores].sort((a, b) => b - a));
  });

  it("applies the country filter", () => {
    const response = searchSitesLocal(
      { power_mw: 1, top_k: 100, country_filter: ["SE"] },
      sites,
    );
    expect(response.results.length).toBeGreaterThan(0);
    expect(response.results.every((r) => r.site.country_code === "SE")).toBe(true);
  });

  it("emits scale-band warnings at the thresholds", () => {
    expect(searchSitesLocal({ power_mw: 10 }, sites).warnings.map((w) => w.code)).toEqual([
      "small_load",
    ]);
    expect(searchSitesLocal({ power_mw: 280 }, sites).warnings).toEqual([]);
    expect(searchSitesLocal({ power_mw: 701 }, sites).warnings.map((w) => w.code)).toEqual([
      "large_load",
    ]);
  });

  it("looks up a site by cell id and rejects unknown cells", () => {
    const sample = sites[0];
    expect(getSiteLocal(sample.cell_id, sites).site.cell_id).toBe(sample.cell_id);
    expect(() => getSiteLocal("not-a-cell", sites)).toThrow(/Unknown site cell/);
  });

  it("returns compared sites in request order", () => {
    const [a, b] = sites;
    const response = compareSitesLocal({ cell_ids: [b.cell_id, a.cell_id] }, sites);
    expect(response.sites.map((s) => s.cell_id)).toEqual([b.cell_id, a.cell_id]);
  });
});
