import { describe, expect, it } from "vitest";

import {
  FINAL_NARRATIVE_CHAR_MS,
  FINAL_NARRATIVE_FADE_S,
  FINAL_NARRATIVE_REVEAL_BUFFER_MS,
  FINAL_NARRATIVE_SETTLE_MS,
  FINAL_NARRATIVE_TOTAL_MS,
  FRED_QUICK_ACK,
  JOURNEY_TIMING,
  NARRATIVE_FADE_S,
  NARRATIVE_LINE_MS,
  NARRATIVE_LINES,
} from "./constants";

describe("journey timing", () => {
  it("gives the final narrative line a slower fade than the others", () => {
    expect(FINAL_NARRATIVE_FADE_S).toBeGreaterThan(NARRATIVE_FADE_S);
  });

  it("reveals the final line character-by-character before settling", () => {
    expect(FINAL_NARRATIVE_CHAR_MS).toBeGreaterThan(0);
    expect(FINAL_NARRATIVE_REVEAL_BUFFER_MS).toBeGreaterThan(0);
    expect(FINAL_NARRATIVE_SETTLE_MS).toBeGreaterThan(0);
    expect(FINAL_NARRATIVE_TOTAL_MS).toBeGreaterThan(NARRATIVE_LINE_MS);
  });

  it("flightMs covers every line plus the final reveal+settle window", () => {
    expect(JOURNEY_TIMING.flightMs).toBe(
      NARRATIVE_LINE_MS * (NARRATIVE_LINES.length - 1) +
        FINAL_NARRATIVE_TOTAL_MS,
    );
  });

  it("ships a short voice ack distinct from the greeting", () => {
    expect(FRED_QUICK_ACK).toBeTypeOf("string");
    expect(FRED_QUICK_ACK.length).toBeGreaterThan(0);
  });
});
