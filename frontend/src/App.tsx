import { Suspense, lazy } from "react";

import { AssumptionsPanel } from "./features/assumptions/AssumptionsPanel";
import { ChatPanel } from "./features/chat/ChatPanel";
import { ComparePanel } from "./features/compare/ComparePanel";
import { SiteMap } from "./features/map/SiteMap";
import { SearchPanel } from "./features/search/SearchPanel";
import { SiteDetailPanel } from "./features/site-detail/SiteDetailPanel";

// OptimizerPanel pulls in Recharts (~50 kB gzipped) and is only relevant after
// a cell is selected. Lazy-loading keeps the initial bundle to the map +
// search shell.
const OptimizerPanel = lazy(() =>
  import("./features/optimizer/OptimizerPanel").then((module) => ({
    default: module.OptimizerPanel,
  })),
);

export function App() {
  return (
    <main className="min-h-screen bg-slate-100 p-3 text-slate-900 sm:p-4">
      <div className="mx-auto grid max-w-[1800px] gap-3 xl:grid-cols-[minmax(0,1fr)_440px]">
        <section className="grid min-w-0 content-start gap-3">
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-normal">
                Loadstar Siting Console
              </h1>
              <p className="mt-1 text-sm text-slate-600">
                Europe · 280 MW demo path
              </p>
            </div>
          </header>
          <div className="grid min-w-0 gap-3 lg:grid-cols-[360px_minmax(0,1fr)]">
            <SearchPanel />
            <SiteMap />
          </div>
          <ComparePanel />
        </section>

        <aside className="grid content-start gap-3 xl:max-h-[calc(100vh-2rem)] xl:overflow-y-auto">
          <SiteDetailPanel />
          <Suspense
            fallback={
              <section className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">
                Loading optimizer...
              </section>
            }
          >
            <OptimizerPanel />
          </Suspense>
          <AssumptionsPanel />
          <ChatPanel />
        </aside>
      </div>
    </main>
  );
}
