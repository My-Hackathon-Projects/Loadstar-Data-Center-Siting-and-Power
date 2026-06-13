/**
 * Pure phase machine for the cinematic entry. Kept free of timers, DOM, and
 * three/r3f so the phase order, the skip-from-every-phase guarantee, and the
 * reduced-motion path can be unit-tested in isolation. The useJourney hook
 * wires real timers and navigation onto this reducer.
 */

export type JourneyPhase =
  | "awaiting"
  | "flight"
  | "arrival"
  | "greeting"
  | "complete";

export type JourneyEvent =
  | { type: "BEGIN" }
  | { type: "ADVANCE" }
  | { type: "SKIP" };

export interface JourneyState {
  phase: JourneyPhase;
  reducedMotion: boolean;
}

const FULL_ORDER: readonly JourneyPhase[] = [
  "awaiting",
  "flight",
  "arrival",
  "greeting",
  "complete",
];

// Reduced motion skips flight and arrival entirely: a single static Europe
// frame (the greeting) fades into the dashboard.
const REDUCED_ORDER: readonly JourneyPhase[] = [
  "awaiting",
  "greeting",
  "complete",
];

function sequence(reducedMotion: boolean): readonly JourneyPhase[] {
  return reducedMotion ? REDUCED_ORDER : FULL_ORDER;
}

/** The phase that follows `phase`; "complete" is terminal. */
export function nextPhase(
  phase: JourneyPhase,
  reducedMotion: boolean,
): JourneyPhase {
  const order = sequence(reducedMotion);
  const index = order.indexOf(phase);
  if (index < 0 || index >= order.length - 1) {
    return "complete";
  }
  return order[index + 1];
}

export function initialJourneyState(reducedMotion: boolean): JourneyState {
  return { phase: "awaiting", reducedMotion };
}

export function journeyReducer(
  state: JourneyState,
  event: JourneyEvent,
): JourneyState {
  switch (event.type) {
    case "BEGIN":
      // Only the awaiting gesture starts the journey.
      if (state.phase !== "awaiting") {
        return state;
      }
      return { ...state, phase: nextPhase("awaiting", state.reducedMotion) };
    case "ADVANCE":
      if (state.phase === "complete") {
        return state;
      }
      return { ...state, phase: nextPhase(state.phase, state.reducedMotion) };
    case "SKIP":
      // A skip control is visible in every phase and jumps straight to /app.
      return { ...state, phase: "complete" };
    default:
      return state;
  }
}
