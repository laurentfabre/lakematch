// Locked deployment build for the APX 0.3.8 app; route/API sources are committed.
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const fromRoot = (path: string) => fileURLToPath(new URL(path, import.meta.url));
export default defineConfig({
  root: fromRoot("./src/lakematch_review/ui"),
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fromRoot("./src/lakematch_review/ui") } },
  build: {
    outDir: fromRoot("./src/lakematch_review/__dist__"),
    emptyOutDir: true,
  },
});
