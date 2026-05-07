import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendTarget = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/health": backendTarget,
      "/media": backendTarget,
      "/events": backendTarget,
      "/result": backendTarget,
      "/run-phase": backendTarget,
      "/run-pipeline": backendTarget,
      "/status": backendTarget,
    },
  },
});
