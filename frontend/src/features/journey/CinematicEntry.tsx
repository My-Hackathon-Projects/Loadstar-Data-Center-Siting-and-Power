import { AnimatePresence, motion } from "framer-motion";
import {
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useMemo,
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
  FINAL_NARRATIVE_CHAR_MS,
  FINAL_NARRATIVE_FADE_S,
  FINAL_NARRATIVE_REVEAL_BUFFER_MS,
  FRED_GREETING,
  FRED_QUICK_ACK,
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

/**
 * Final-line reveal: each character is a span with staggered opacity. The
 * earlier lines stay on the simple AnimatePresence fade-swap path. This is the
 * difference between "the climax line lands" and "the climax line cuts to the
 * globe" — the latter is what the demo previously felt like.
 */
function FinalNarrativeLine({ text }: { text: string }) {
  const characters = useMemo(
    () =>
      Array.from(text).map((char) => (char === " " ? " " : char)),
    [text],
  );

  return (
    <motion.p
      animate={{ opacity: 1 }}
      className="px-8 text-center text-2xl font-light tracking-wide text-primary sm:text-3xl"
      exit={{ opacity: 0 }}
      initial={{ opacity: 0 }}
      transition={{
        duration: FINAL_NARRATIVE_FADE_S,
        ease: EASE_OUT,
      }}
    >
      <motion.span
        animate="visible"
        aria-label={text}
        initial="hidden"
        style={{ display: "inline-block" }}
        transition={{
          delayChildren: FINAL_NARRATIVE_REVEAL_BUFFER_MS / 1000,
          staggerChildren: FINAL_NARRATIVE_CHAR_MS / 1000,
        }}
      >
        {characters.map((char, idx) => (
          <motion.span
            aria-hidden
            key={idx}
            style={{ display: "inline-block", whiteSpace: "pre" }}
            transition={{ duration: 0.18, ease: EASE_OUT }}
            variants={{
              hidden: { opacity: 0 },
              visible: { opacity: 1 },
            }}
          >
            {char}
          </motion.span>
        ))}
      </motion.span>
    </motion.p>
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

  const finalIndex = NARRATIVE_LINES.length - 1;
  const isFinal = index === finalIndex;

  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
      <AnimatePresence mode="wait">
        {isFinal ? (
          <FinalNarrativeLine
            key="final"
            text={NARRATIVE_LINES[finalIndex] ?? ""}
          />
        ) : (
          <motion.p
            animate={{ opacity: 1 }}
            className="px-8 text-center text-2xl font-light tracking-wide text-primary sm:text-3xl"
            exit={{ opacity: 0 }}
            initial={{ opacity: 0 }}
            key={index}
            transition={{
              duration: NARRATIVE_FADE_S,
              ease: EASE_OUT,
            }}
          >
            {NARRATIVE_LINES[index]}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}

const HANDOFF_TIMEOUT_MS = 6000;

function Greeting({ onCommand }: { onCommand: () => void }) {
  const greetedRef = useRef(false);
  const submittedRef = useRef(false);
  const [isThinking, setIsThinking] = useState(false);

  const submitCommand = useCallback(
    (rawCommand: string) => {
      const command = rawCommand.trim();
      if (!command || submittedRef.current) {
        return;
      }
      submittedRef.current = true;
      setIsThinking(true);

      // Hand the prompt to the dashboard and let it run the agent after it
      // mounts. The agent call can take 20s+ (a thinking model), far longer
      // than the cinematic ack below, so running it here and racing navigation
      // would drop the result and the dashboard would lose the question. The
      // dashboard owns the call via runAgent, the same path the chat input uses.
      savePendingFredPrompt(command);

      // Speak the short ack and advance when the audio ends.
      let advanced = false;
      const advance = () => {
        if (advanced) {
          return;
        }
        advanced = true;
        onCommand();
      };

      void speakFred(FRED_QUICK_ACK, { onEnd: advance });
      // Hard backstop in case ElevenLabs never fires onEnd.
      window.setTimeout(advance, HANDOFF_TIMEOUT_MS);
    },
    [onCommand],
  );

  const speech = useSpeechInput({ onFinalTranscript: submitCommand });
  const {
    error: speechError,
    listening,
    start,
    supported,
    transcript,
  } = speech;

  useEffect(() => {
    if (greetedRef.current) {
      return;
    }
    greetedRef.current = true;
    void speakFred(FRED_GREETING, {
      onEnd: () => {
        if (submittedRef.current) {
          return;
        }
        start();
      },
    });
  }, [start]);

  const statusText = !supported
    ? "voice input is unavailable in this browser"
    : isThinking
      ? "thinking..."
      : listening
        ? transcript || "listening..."
        : "waiting for voice...";

  return (
    <motion.div
      className="absolute inset-x-0 bottom-0 flex justify-center pb-[12vh]"
      {...fade}
    >
      <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-2xl border border-subtle bg-panel px-6 py-6">
        <VoiceBars active={listening || isThinking} bars={6} />
        <p className="text-center text-lg text-primary">{FRED_GREETING}</p>
        <div className="min-h-10 w-full rounded-full border border-subtle bg-void px-4 py-2.5 text-center text-sm text-dim">
          {statusText}
        </div>
        {speechError ? (
          <p className="text-center text-xs text-dim">{speechError}</p>
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
            animate={{ opacity: 1 }}
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
