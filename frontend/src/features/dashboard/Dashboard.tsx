import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useSearchRequest } from "../../hooks/useSearchRequest";
import { useUiStore } from "../../hooks/useUiStore";
import { useSearchSites } from "../../lib/queries";
import { FredPanel } from "../chat/FredPanel";
import { SiteMap } from "../map/SiteMap";
import { DetailDrawer } from "./DetailDrawer";
import { SpecificationsBar } from "./SpecificationsBar";
import { StatsStrip } from "./StatsStrip";

export default function Dashboard() {
  const [specsOpen, setSpecsOpen] = useState(true);
  const [detailOpen, setDetailOpen] = useState(false);

  const search = useSearchSites(useSearchRequest());
  const results = search.data?.results;
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);

  // Keep a valid selection: pick the top result when none is selected or the
  // current one drops out of the results (e.g. after Fred narrows the search).
  useEffect(() => {
    const first = results?.[0]?.site.cell_id;
    const stillVisible =
      results?.some((result) => result.site.cell_id === selectedCellId) ?? false;
    if (first && (!selectedCellId || !stillVisible)) {
      setSelectedCellId(first);
    }
    if (!first && selectedCellId) {
      setSelectedCellId(null);
    }
  }, [results, selectedCellId, setSelectedCellId]);

  const columns = specsOpen
    ? "lg:grid-cols-[300px_minmax(0,1fr)_360px]"
    : "lg:grid-cols-[48px_minmax(0,1fr)_360px]";

  return (
    <main className="flex h-screen flex-col gap-3 overflow-y-auto bg-void p-3 text-primary sm:p-4 lg:overflow-hidden">
      <header className="flex items-center justify-between">
        <div className="flex items-baseline gap-3">
          <span className="text-sm lowercase tracking-[0.3em] text-dim">
            loadstar
          </span>
          <span className="text-xs text-faint">europe · siting console</span>
        </div>
        <nav className="flex items-center gap-4 text-xs lowercase tracking-wide text-dim">
          <button
            className="transition-colors hover:text-primary"
            onClick={() => setDetailOpen(true)}
            type="button"
          >
            site detail
          </button>
          <Link className="transition-colors hover:text-primary" to="/tech">
            behind the tech
          </Link>
          <Link className="transition-colors hover:text-accent" to="/thanks">
            end the journey
          </Link>
        </nav>
      </header>

      <div
        className={`grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-rows-1 ${columns}`}
      >
        <SpecificationsBar
          onToggle={() => setSpecsOpen((open) => !open)}
          open={specsOpen}
        />
        <SiteMap />
        <FredPanel />
      </div>

      <StatsStrip />

      <DetailDrawer onClose={() => setDetailOpen(false)} open={detailOpen} />
    </main>
  );
}
