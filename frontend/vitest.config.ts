import { defineConfig } from "vitest/config";

// Unit tests live in src/ and are pure (no DOM rendering), so no plugins are
// needed. The e2e/ directory holds Playwright specs and must be excluded — its
// test() runs under Playwright, not Vitest.
export default defineConfig({
  test: {
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
  },
});
