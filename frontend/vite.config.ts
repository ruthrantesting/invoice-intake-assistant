import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const prototypeMode = process.env.VITE_PROTOTYPE_MODE === "true";

export default defineConfig({
  plugins: [react()],
  define: { __PROTOTYPE_MODE__: JSON.stringify(prototypeMode) },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
