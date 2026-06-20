import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import cesium from "vite-plugin-cesium";

export default defineConfig({
  plugins: [react(), cesium()],
  server: {
    port: 5173,
    open: true,
    // allow importing the shared ../data/*.json (single source of truth)
    fs: { allow: [".."] },
  },
});
