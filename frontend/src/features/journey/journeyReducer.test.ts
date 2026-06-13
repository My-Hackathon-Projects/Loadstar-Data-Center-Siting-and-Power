import { describe, expect, it } from "vitest";

import {
  initialJourneyState,
  journeyReducer,
  nextPhase,
  type JourneyPhase,
  type JourneyState,
} from "./journeyReducer";

describe("journeyReducer", () => {
  it("advances through the full phase order then stays complete", () => {
    let state = initialJourneyState(false);
    expect(state.phase).toBe("awaiting");

    state = journeyReducer(state, { type: "BEGIN" });
    expect(state.phase).toBe("flight");
    state = journeyReducer(state, { type: "ADVANCE" });
    expect(state.phase).toBe("arrival");
    state = journeyReducer(state, { type: "ADVANCE" });
    expect(state.phase).toBe("greeting");
    state = journeyReducer(state, { type: "ADVANCE" });
    expect(state.phase).toBe("complete");

    // complete is terminal.
    state = journeyReducer(state, { type: "ADVANCE" });
    expect(state.phase).toBe("complete");
  });

  it("skips flight and arrival under reduced motion", () => {
    let state = initialJourneyState(true);
    state = journeyReducer(state, { type: "BEGIN" });
    expect(state.phase).toBe("greeting");
    state = journeyReducer(state, { type: "ADVANCE" });
    expect(state.phase).toBe("complete");
  });

  it("skips straight to complete from every phase", () => {
    const phases: JourneyPhase[] = ["awaiting", "flight", "arrival", "greeting"];
    for (const phase of phases) {
      const state: JourneyState = { phase, reducedMotion: false };
      expect(journeyReducer(state, { type: "SKIP" }).phase).toBe("complete");
    }
  });

  it("only starts the journey with BEGIN from awaiting", () => {
    const midFlight: JourneyState = { phase: "flight", reducedMotion: false };
    expect(journeyReducer(midFlight, { type: "BEGIN" })).toBe(midFlight);
  });

  it("nextPhase reflects order and reduced-motion skips", () => {
    expect(nextPhase("awaiting", false)).toBe("flight");
    expect(nextPhase("greeting", false)).toBe("complete");
    expect(nextPhase("complete", false)).toBe("complete");
    expect(nextPhase("awaiting", true)).toBe("greeting");
  });
});
