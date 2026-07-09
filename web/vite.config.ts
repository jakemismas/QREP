/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// base "./" keeps every asset reference relative so the same build works at
// the Pages subpath (/QREP/app/) and at a local preview root.
export default defineConfig({
  base: "./",
  plugins: [react()],
  worker: {
    format: "es",
  },
  build: {
    rollupOptions: {
      // Two pages: the app at the root, the S0 spike page kept reachable at
      // /spike.html for the gate e2e.
      input: {
        main: "index.html",
        spike: "spike.html",
      },
    },
  },
  test: {
    passWithNoTests: true,
    exclude: ["e2e/**", "node_modules/**"],
  },
});
