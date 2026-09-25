// @ts-check
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://abrunacci.dev",
  build: {
    // The server caches /assets/ for a year, so only files whose names change
    // with their content (Astro adds a hash) may go there.
    assets: "assets",
    // One page and a few KB of CSS: inlining saves a request on first visit.
    inlineStylesheets: "always",
  },
});
