import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
  server: {
    proxy: {
      "/api": "http://backend:8000",
      "/health": "http://backend:8000",
    },
  },
});
