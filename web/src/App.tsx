import { OptimizerPanel } from "./features/optimizer/OptimizerPanel";
import { SearchPanel } from "./features/search/SearchPanel";
import { SiteMap } from "./features/map/SiteMap";
import { SiteDetailPanel } from "./features/site-detail/SiteDetailPanel";

export function App() {
  return (
    <main className="min-h-screen bg-slate-100 p-4 text-slate-900">
      <div className="grid min-h-[calc(100vh-2rem)] gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-4 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-normal">Loadstar</h1>
              <p className="mt-1 text-sm text-slate-600">
                Fixture skeleton for data-center siting and power planning.
              </p>
            </div>
            <SearchPanel />
          </div>
          <SiteMap />
        </section>

        <aside className="grid content-start gap-4">
          <SiteDetailPanel />
          <OptimizerPanel />
        </aside>
      </div>
    </main>
  );
}
