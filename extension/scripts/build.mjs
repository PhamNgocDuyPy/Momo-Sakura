// Builds the extension into dist/:
//  1. background.js  - ES module service worker (single file, public/ copied here)
//  2. content.js     - classic-script IIFE, CSS inlined into the Shadow DOM at runtime
//  3. options.html   - options page (+ assets/)
import { build } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const common = {
  root,
  configFile: false,
  logLevel: "warn",
  plugins: [react()],
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
};

await build({
  ...common,
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2022",
    lib: { entry: resolve(root, "src/background.ts"), formats: ["es"], fileName: () => "background.js" },
  },
});

await build({
  ...common,
  publicDir: false,
  build: {
    outDir: "dist",
    emptyOutDir: false,
    target: "es2022",
    lib: {
      entry: resolve(root, "src/content/mount.tsx"),
      formats: ["iife"],
      name: "MomoGuardianContent",
      fileName: () => "content.js",
    },
  },
});

await build({
  ...common,
  publicDir: false,
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: false,
    target: "es2022",
    rollupOptions: { input: resolve(root, "options.html") },
  },
});

console.log("Extension built into extension/dist");