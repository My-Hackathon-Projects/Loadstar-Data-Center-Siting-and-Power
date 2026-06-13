import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
const API_TARGET = "http://127.0.0.1:8000";
// `envDir: ".."` points Vite at the single root `.env` so `VITE_API_BASE_URL`
// (and any future `VITE_*` keys) live alongside the backend's secrets in one
// place. The frontend never reads non-`VITE_*` keys, so backend-only secrets
// stay private to the API process.
export default defineConfig({
    envDir: "..",
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            "/agent": API_TARGET,
            "/assumptions": API_TARGET,
            "/health": API_TARGET,
            // Pre-computed overlays live under public/layers/*.json. In production
            // (no proxy) Vite serves them as static assets and the SPA prefers them.
            // In dev the proxy would otherwise shadow them and 404 against the live
            // API, which only exposes the extension-less `/layers/{name}` route. The
            // bypass returns the request path for `.json` so Vite serves the static
            // file; everything else proxies to the live API.
            "/layers": {
                target: API_TARGET,
                bypass(req) {
                    const path = req.url?.split("?")[0];
                    if (path && path.endsWith(".json")) {
                        return req.url;
                    }
                },
            },
            "/meta": API_TARGET,
            "/optimize": API_TARGET,
            "/sites": API_TARGET,
        },
    },
});
