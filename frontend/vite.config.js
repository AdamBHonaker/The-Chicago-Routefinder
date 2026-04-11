import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon-192.png", "icon-512.png", "apple-touch-icon.png"],
      manifest: {
        name: "CTA Transit",
        short_name: "CTA Transit",
        description: "AI-powered real-time CTA route recommendations for Chicago riders.",
        theme_color: "#1a5bad",
        background_color: "#0a0a0a",
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
            src: "icon-512.png",
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
            // Match /recommend and /health regardless of hostname (covers both
            // localhost dev and the production Railway URL)
            urlPattern: /\/(recommend|health)(\?.*)?$/i,
            handler: "NetworkOnly",
          },
          {
            // Transit photos: serve from cache if available, update in background
            urlPattern: /\/transit-photos\//i,
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "transit-photos",
              expiration: { maxEntries: 30, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
  },
});
