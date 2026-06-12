import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            "/health": "http://127.0.0.1:8000",
            "/layers": "http://127.0.0.1:8000",
            "/sites": "http://127.0.0.1:8000",
            "/optimize": "http://127.0.0.1:8000",
            "/assumptions": "http://127.0.0.1:8000"
        }
    }
});
