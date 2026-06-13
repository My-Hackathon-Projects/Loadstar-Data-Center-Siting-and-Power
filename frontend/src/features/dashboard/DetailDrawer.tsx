import { AnimatePresence, motion } from "framer-motion";
import { Suspense, lazy } from "react";

import { ComparePanel } from "../compare/ComparePanel";
import { SiteDetailPanel } from "../site-detail/SiteDetailPanel";

// OptimizerPanel pulls in Recharts; lazy-load it so that cost lands only when
// the drawer first opens, not in the /app entry bundle.
const OptimizerPanel = lazy(() =>
  import("../optimizer/OptimizerPanel").then((module) => ({
    default: module.OptimizerPanel,
  })),
);

const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];

interface DetailDrawerProps {
  open: boolean;
  onClose: () => void;
}

/** Slide-in drawer holding site detail, the optimizer, and the comparison view. */
export function DetailDrawer({ open, onClose }: DetailDrawerProps) {
  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            animate={{ opacity: 1 }}
            className="fixed inset-0 z-30 bg-scrim"
            exit={{ opacity: 0 }}
            initial={{ opacity: 0 }}
            onClick={onClose}
            transition={{ duration: 0.3 }}
          />
          <motion.aside
            animate={{ x: 0 }}
            className="fixed right-0 top-0 z-40 flex h-full w-full max-w-md flex-col gap-4 overflow-y-auto border-l border-subtle bg-panel p-5"
            exit={{ x: "100%" }}
            initial={{ x: "100%" }}
            transition={{ duration: 0.5, ease: EASE_OUT }}
          >
            <div className="flex items-center justify-between">
              <p className="eyebrow">site detail</p>
              <button
                className="text-sm lowercase tracking-wide text-dim transition-colors hover:text-primary"
                onClick={onClose}
                type="button"
              >
                close
              </button>
            </div>
            <SiteDetailPanel />
            <Suspense
              fallback={<p className="text-sm text-dim">Loading optimizer...</p>}
            >
              <OptimizerPanel />
            </Suspense>
            <ComparePanel />
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}
