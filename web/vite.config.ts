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
  test: {
    passWithNoTests: true,
    exclude: ["e2e/**", "node_modules/**"],
  },
});
