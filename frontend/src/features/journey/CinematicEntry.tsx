import { AnimatePresence, motion } from "framer-motion";
import { Suspense, lazy, useEffect, useState } from "react";

import { COUNTRIES_URL } from "../map/darkBasemap";
import { SkipControl } from "./SkipControl";
import { VoiceBars } from "./VoiceBars";
import {
  CROSSFADE_S,
  EASE_OUT,
  FRED_GREETING,
  JOURNEY_TIMING,
  NARRATIVE_LINES,
  PRODUCT_NAME,
} from "./constants";
import { useJourney } from "./useJourney";

// Flight is the only consumer of three / @react-three/fiber. Lazy-loading it
// keeps three in a /-only chunk and avoids fetching it at all for reduced-motion
// visitors, who never enter the flight phase.
const Flight = lazy(() => import("./phases/Flight"));
const GlobeStage = lazy(() => import("./phases/GlobeStage"));

const fade = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: CROSSFADE_S, ease: EASE_OUT },
};

function Awaiting({ onBegin }: { onBegin: () => void }) {
  return (
    <motion.div
      className="absolute inset-0 flex flex-col items-center justify-center gap-12"
      {...fade}
    >
      <p className="text-sm font-light lowercase tracking-[0.4em] text-dim">
        {PRODUCT_NAME}
      </p>
      <button
        className="rounded-full border border-strong px-7 py-2.5 text-sm lowercase tracking-wide text-primary transition-colors hover:border-accent hover:text-accent"
        onClick={onBegin}
        type="button"
      >
        begin the journey
      </button>
    </motion.div>
  );
}

function FlightNarrative() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const perLine = JOURNEY_TIMING.flightMs / NARRATIVE_LINES.length;
    const timer = window.setInterval(() => {
      setIndex((current) => Math.min(current + 1, NARRATIVE_LINES.length - 1));
    }, perLine);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
      <AnimatePresence mode="wait">
        <motion.p
          animate={{ opacity: 1 }}
          className="px-8 text-center text-2xl font-light tracking-wide text-primary sm:text-3xl"
          exit={{ opacity: 0 }}
          initial={{ opacity: 0 }}
          key={index}
          transition={{ duration: 0.85, ease: EASE_OUT }}
        >
          {NARRATIVE_LINES[index]}
        </motion.p>
      </AnimatePresence>
    </div>
  );
}

function Greeting() {
  return (
    <motion.div
      className="absolute inset-x-0 bottom-0 flex justify-center pb-[12vh]"
      {...fade}
    >
      <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-2xl border border-subtle bg-panel px-6 py-6">
        <VoiceBars active bars={6} />
        <p className="text-center text-lg text-primary">{FRED_GREETING}</p>
        <input
          autoFocus
          className="w-full rounded-full border border-subtle bg-void px-4 py-2.5 text-center text-sm text-primary outline-none placeholder:text-faint focus:border-accent"
          placeholder="ask fred"
          readOnly
        />
      </div>
    </motion.div>
  );
}

export default function CinematicEntry() {
  const { phase, reducedMotion, begin, skip } = useJourney();
  const showGlobe = phase === "arrival" || phase === "greeting";

  // Warm the basemap geometry during flight so the globe handoff never stutters.
  useEffect(() => {
    if (phase === "flight") {
      void fetch(COUNTRIES_URL).catch(() => undefined);
    }
  }, [phase]);

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-void text-primary">
      <AnimatePresence>
        {phase === "flight" && (
          <motion.div className="absolute inset-0" key="flight" {...fade}>
            <Suspense fallback={null}>
              <Flight />
            </Suspense>
          </motion.div>
        )}
        {showGlobe && (
          <motion.div
            animate={{ opacity: 1, y: phase === "greeting" ? "-5%" : "0%" }}
            className="absolute inset-0"
            exit={{ opacity: 0 }}
            initial={{ opacity: 0 }}
            key="globe"
            transition={{ duration: CROSSFADE_S, ease: EASE_OUT }}
          >
            <Suspense fallback={null}>
              <GlobeStage animate={!reducedMotion} />
            </Suspense>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {phase === "awaiting" && <Awaiting key="awaiting" onBegin={begin} />}
        {phase === "flight" && <FlightNarrative key="narrative" />}
        {phase === "greeting" && <Greeting key="greeting" />}
      </AnimatePresence>

      <SkipControl onSkip={skip} />
    </main>
  );
}
