import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
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
            "/agent": "http://127.0.0.1:8000",
            "/assumptions": "http://127.0.0.1:8000",
            "/health": "http://127.0.0.1:8000",
            "/layers": "http://127.0.0.1:8000",
            "/meta": "http://127.0.0.1:8000",
            "/optimize": "http://127.0.0.1:8000",
            "/sites": "http://127.0.0.1:8000",
        },
    },
});
