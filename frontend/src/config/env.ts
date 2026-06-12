/// <reference types="vite/client" />

/**
 * Base URL the React app uses for REST calls.
 *
 * Empty string keeps requests same-origin:
 *   - dev: handled by the Vite proxy in `vite.config.ts`
 *   - prod: served by FastAPI from the same origin as the SPA
 *
 * Set `VITE_API_BASE_URL` in `frontend/.env` to point at a different host
 * during local development against a remote API.
 */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "";
