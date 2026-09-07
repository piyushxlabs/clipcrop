import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  server: {
    port: 5173,
    proxy: {
      "/runs": "http://127.0.0.1:8000",
      "/outputs": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});

