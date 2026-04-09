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
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        // Cache the app shell; API calls always go to the network
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        runtimeCaching: [
          {
            // Match /recommend and /health regardless of hostname (covers both
            // localhost dev and the production Railway URL)
            urlPattern: /\/(recommend|health)(\?.*)?$/i,
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
  },
});
