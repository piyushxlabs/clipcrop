import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/runs": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/outputs": "http://127.0.0.1:8000",
    },
  },
  esbuild: {
    jsx: "automatic",
  },
});
