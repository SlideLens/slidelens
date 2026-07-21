import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    // Defaults match plain `npm run dev` on the host (API in Docker on :8000).
    host: process.env.VITE_DEV_HOST ?? "127.0.0.1",
    port: 5173,
    strictPort: true,
    hmr: { clientPort: 5173 },
    watch: process.env.VITE_WATCH_POLL ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
