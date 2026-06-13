import { describe, expect, it } from "vitest";

import {
  FINAL_NARRATIVE_FADE_S,
  FINAL_NARRATIVE_HOLD_MS,
  JOURNEY_TIMING,
  NARRATIVE_FADE_S,
  NARRATIVE_LINE_MS,
  NARRATIVE_LINES,
} from "./constants";

describe("journey timing", () => {
  it("gives the final narrative line a slower fade and a dedicated hold", () => {
    expect(FINAL_NARRATIVE_FADE_S).toBeGreaterThan(NARRATIVE_FADE_S);
    expect(FINAL_NARRATIVE_HOLD_MS).toBeGreaterThan(NARRATIVE_LINE_MS);
    expect(JOURNEY_TIMING.flightMs).toBe(
      NARRATIVE_LINE_MS * (NARRATIVE_LINES.length - 1) +
        FINAL_NARRATIVE_HOLD_MS,
    );
  });
});
