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
        // Cache app shell assets. PNG glob restricted to PWA icons only so
        // any future bitmap content added under public/ (transit photos,
        // illustrations, etc.) is not pre-cached into the service worker
        // manifest — that risks hitting the ~50 MB storage quota on older
        // Android WebViews. Lazy assets should be loaded at runtime under
        // a StaleWhileRevalidate handler instead.
        globPatterns: [
          "**/*.{js,css,html,ico,svg,woff2}",
          "icon-*.png",
          "apple-touch-icon.png",
        ],
        runtimeCaching: [
          {
            // Map style document + sprite/glyph metadata from OpenFreemap.
            // Small, changes rarely — SWR keeps the cold open instant while
            // still picking up upstream style edits within a session.
            urlPattern: ({ url }) =>
              url.origin === "https://tiles.openfreemap.org" &&
              (url.pathname.startsWith("/styles/") ||
               url.pathname.includes("/sprites/") ||
               url.pathname.includes("/fonts/")),
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "map-style",
              expiration: {
                maxEntries: 60,
                maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
              },
            },
          },
          {
            // Vector tile PBFs — bounded cache for the area the user pans.
            // CacheFirst: tile bytes are content-addressed by z/x/y and
            // effectively immutable, so SWR would waste battery on
            // background refetches. Responses are opaque cross-origin (no
            // CORS), so Workbox sees status 0 — allow it explicitly.
            urlPattern: ({ url }) =>
              url.origin === "https://tiles.openfreemap.org" &&
              /\.pbf$/i.test(url.pathname),
            handler: "CacheFirst",
            options: {
              cacheName: "map-tiles",
              expiration: {
                maxEntries: 400,                  // ~25 MB ceiling
                maxAgeSeconds: 60 * 60 * 24 * 14, // 14 days
                purgeOnQuotaError: true,
              },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
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
    // host: true binds to 0.0.0.0 so a phone on the same Wi-Fi can hit
    // http://<dev-machine-LAN-IP>:5173. Vite prints the LAN URL on startup.
    host: true,
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
