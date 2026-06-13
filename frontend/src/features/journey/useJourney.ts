import { useEffect, useReducer, useState } from "react";
import { useNavigate } from "react-router-dom";

import { JOURNEY_TIMING } from "./constants";
import {
  initialJourneyState,
  journeyReducer,
  type JourneyPhase,
} from "./journeyReducer";

/** Phases that auto-advance on a timer. Awaiting is gesture-gated; complete navigates. */
const PHASE_DURATION_MS: Partial<Record<JourneyPhase, number>> = {
  flight: JOURNEY_TIMING.flightMs,
  arrival: JOURNEY_TIMING.arrivalMs,
  greeting: JOURNEY_TIMING.greetingMs,
};

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function usePrefersReducedMotion(): boolean {
  const [reduced] = useState(prefersReducedMotion);
  return reduced;
}

export interface Journey {
  phase: JourneyPhase;
  reducedMotion: boolean;
  begin: () => void;
  skip: () => void;
}

/**
 * Owns journey timing and the commit to /app. Phase transitions fire on timers,
 * never on a network fetch, so no request can block the cinematic pacing.
 */
export function useJourney(): Journey {
  const navigate = useNavigate();
  const reducedMotion = usePrefersReducedMotion();
  const [state, dispatch] = useReducer(
    journeyReducer,
    reducedMotion,
    initialJourneyState,
  );

  useEffect(() => {
    const duration = PHASE_DURATION_MS[state.phase];
    if (duration == null) {
      return;
    }
    const timer = window.setTimeout(() => dispatch({ type: "ADVANCE" }), duration);
    return () => window.clearTimeout(timer);
  }, [state.phase]);

  useEffect(() => {
    if (state.phase === "complete") {
      navigate("/app", { replace: true });
    }
  }, [state.phase, navigate]);

  return {
    phase: state.phase,
    reducedMotion: state.reducedMotion,
    begin: () => dispatch({ type: "BEGIN" }),
    skip: () => dispatch({ type: "SKIP" }),
  };
}
