import { defineConfig, devices } from "@playwright/test";

const PORT = 5180;
const BASE_URL = `http://127.0.0.1:${PORT}`;

// Two servers back the demo-path test: the FastAPI backend and the Vite dev
// server (which proxies the API). `reuseExistingServer` lets a local `make dev`
// stack satisfy these so the test does not double-bind ports. Kept out of
// `make test` because it boots servers rather than running as a unit gate.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: "list",
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "python3 -m uvicorn backend.api.main:app --port 8000",
      cwd: "..",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: `npm run dev -- --port ${PORT} --strictPort`,
      url: BASE_URL,
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
