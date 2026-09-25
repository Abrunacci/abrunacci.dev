// @ts-check
import { defineConfig, fontProviders } from "astro/config";

export default defineConfig({
  site: "https://abrunacci.dev",
  build: {
    // The server caches /assets/ for a year, so only files whose names change
    // with their content (Astro adds a hash) may go there.
    assets: "assets",
    // One page and a few KB of CSS: inlining saves a request on first visit.
    inlineStylesheets: "always",
  },
  fonts: [
    {
      // Self-hosted from the npm package: the build downloads nothing. Astro
      // also generates a fallback with matching metrics, so text does not
      // jump when Inter arrives.
      provider: fontProviders.local(),
      name: "Inter",
      cssVariable: "--font-inter",
      fallbacks: ["system-ui", "sans-serif"],
      options: {
        variants: [
          {
            src: ["@fontsource-variable/inter/files/inter-latin-wght-normal.woff2"],
            weight: "100 900",
            style: "normal",
            display: "swap",
          },
        ],
      },
    },
  ],
});
