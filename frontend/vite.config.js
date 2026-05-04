import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
// Vitest types are referenced via vite.config.js — no separate vitest.config needed.

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: [
        "icon-192.png",
        "icon-512.png",
        "icon-512-maskable.png",
        "apple-touch-icon.png",
      ],
      manifest: {
        name: "The Chicago Routefinder",
        short_name: "Routefinder",
        description: "A working guide to the trains, buses, and schedules of the city.",
        theme_color: "#171310",
        background_color: "#f2ece0",
        display: "standalone",
        orientation: "portrait",
        scope: "/",
        start_url: "/",
        icons: [
          {
            src: "icon-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "icon-512-maskable.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        // Cache app shell assets. Restrict PNGs to icons only so high-res
        // transit photos are NOT pre-cached (they would add 20–50 MB to the
        // service worker manifest and risk hitting the ~50 MB storage quota
        // on older Android WebViews). Transit photos are fetched lazily at
        // runtime via StaleWhileRevalidate instead.
        globPatterns: [
          "**/*.{js,css,html,ico,svg,woff2}",
          "icon-*.png",
          "apple-touch-icon.png",
        ],
        runtimeCaching: [
          {
            // Never cache /recommend: responses contain user origin/destination
            // and (when BYOK is enabled) reflect a request body containing the
            // user's Anthropic API key. Caching that data — especially across
            // shared devices — is a privacy and credential-leakage risk.
            urlPattern: /\/recommend(\?.*)?$/i,
            handler: "NetworkOnly",
          },
          {
            // /health is non-sensitive; keep cached so the app shell can show
            // an offline indicator quickly when the network is unavailable.
            urlPattern: /\/health(\?.*)?$/i,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-cache",
              expiration: {
                maxEntries: 5,
                maxAgeSeconds: 3600,
              },
            },
          },
        ],
      },
    }),
  ],
  build: {
    // Don't ship source maps to production — they expose unminified source +
    // file structure to anyone opening DevTools.
    sourcemap: false,
    rollupOptions: {
      output: {
        // Split heavy vendors into their own chunks so the browser can
        // parallelize downloads, and so a deploy that only changes app code
        // doesn't invalidate the (large + rarely-changing) vendor caches.
        // maplibre-gl is intentionally NOT listed here: it's already
        // dynamically imported from MapView.jsx via React.lazy in App.jsx,
        // so Rollup gives it its own chunk automatically.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("react-dom") || /[\\/]react[\\/]/.test(id) || id.includes("scheduler")) {
            return "react-vendor";
          }
          if (id.includes("i18next") || id.includes("react-i18next")) {
            return "i18n-vendor";
          }
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/tests/**/*.test.{js,jsx}"],
    setupFiles: ["src/tests/setup.js"],
    coverage: {
      provider: "v8",
      include: ["src/utils/**", "src/hooks/**", "src/favorites.js", "src/components/**"],
    },
  },
});
