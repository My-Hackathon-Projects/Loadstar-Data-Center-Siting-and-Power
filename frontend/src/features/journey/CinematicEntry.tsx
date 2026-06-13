import { AnimatePresence, motion } from "framer-motion";
import {
  FormEvent,
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { useSpeechInput } from "../../hooks/useSpeechInput";
import { savePendingFredPrompt } from "../../lib/fredPrompt";
import { speakFred } from "../../lib/fredVoice";
import { COUNTRIES_URL } from "../map/darkBasemap";
import { SkipControl } from "./SkipControl";
import { VoiceBars } from "./VoiceBars";
import {
  CROSSFADE_S,
  EASE_OUT,
  FINAL_NARRATIVE_FADE_S,
  FRED_GREETING,
  NARRATIVE_FADE_S,
  NARRATIVE_LINE_MS,
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
    if (index >= NARRATIVE_LINES.length - 1) {
      return;
    }
    const timer = window.setTimeout(() => {
      setIndex((current) => current + 1);
    }, NARRATIVE_LINE_MS);
    return () => window.clearTimeout(timer);
  }, [index]);

  const finalLine = index === NARRATIVE_LINES.length - 1;

  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
      <AnimatePresence mode="wait">
        <motion.p
          animate={{ opacity: 1 }}
          className="px-8 text-center text-2xl font-light tracking-wide text-primary sm:text-3xl"
          exit={{ opacity: 0 }}
          initial={{ opacity: 0 }}
          key={index}
          transition={{
            duration: finalLine ? FINAL_NARRATIVE_FADE_S : NARRATIVE_FADE_S,
            ease: EASE_OUT,
          }}
        >
          {NARRATIVE_LINES[index]}
        </motion.p>
      </AnimatePresence>
    </div>
  );
}

function Greeting({ onCommand }: { onCommand: () => void }) {
  const [draft, setDraft] = useState("");
  const greetedRef = useRef(false);

  const submitCommand = useCallback(
    (rawCommand: string) => {
      const command = rawCommand.trim();
      if (!command) {
        return;
      }
      savePendingFredPrompt(command);
      onCommand();
    },
    [onCommand],
  );

  const speech = useSpeechInput({ onFinalTranscript: submitCommand });

  useEffect(() => {
    if (greetedRef.current) {
      return;
    }
    greetedRef.current = true;
    speakFred(FRED_GREETING);
  }, []);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitCommand(draft);
  }

  const visibleDraft = speech.listening && speech.transcript ? speech.transcript : draft;

  return (
    <motion.div
      className="absolute inset-x-0 bottom-0 flex justify-center pb-[12vh]"
      {...fade}
    >
      <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-2xl border border-subtle bg-panel px-6 py-6">
        <VoiceBars active={speech.listening} bars={6} />
        <p className="text-center text-lg text-primary">{FRED_GREETING}</p>
        <form className="flex w-full gap-2" onSubmit={handleSubmit}>
          <input
            autoFocus
            className="min-w-0 flex-1 rounded-full border border-subtle bg-void px-4 py-2.5 text-center text-sm text-primary outline-none placeholder:text-faint focus:border-accent"
            onChange={(event) => setDraft(event.target.value)}
            placeholder="ask fred"
            value={visibleDraft}
          />
          {speech.supported ? (
            <button
              aria-label={speech.listening ? "stop voice input" : "start voice input"}
              className="rounded-full border border-subtle px-3 py-2.5 text-xs lowercase text-dim transition-colors hover:border-accent hover:text-accent"
              onClick={speech.toggle}
              type="button"
            >
              {speech.listening ? "stop" : "voice"}
            </button>
          ) : null}
          <button
            className="rounded-full bg-accent px-4 py-2.5 text-sm font-medium text-accent-contrast transition-opacity disabled:opacity-40"
            disabled={!visibleDraft.trim()}
            type="submit"
          >
            ask
          </button>
        </form>
        {speech.error ? (
          <p className="text-center text-xs text-dim">{speech.error}</p>
        ) : null}
      </div>
    </motion.div>
  );
}

export default function CinematicEntry() {
  const { phase, reducedMotion, begin, finish, skip } = useJourney();
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
        {phase === "greeting" && <Greeting key="greeting" onCommand={finish} />}
      </AnimatePresence>

      <SkipControl onSkip={skip} />
    </main>
  );
}
