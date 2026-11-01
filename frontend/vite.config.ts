/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "SafeTrail",
        short_name: "SafeTrail",
        description: "Trail safety companion for treks, pilgrimages and national parks",
        theme_color: "#0f766e",
        background_color: "#f6f5f1",
        display: "standalone",
        start_url: "/",
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
      },
      workbox: {
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//],
        globPatterns: ["**/*.{js,css,html,svg,woff2}"],
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/tile\.openstreetmap\.org\//,
            handler: "CacheFirst",
            options: { cacheName: "map-tiles", expiration: { maxEntries: 300, maxAgeSeconds: 7 * 86400 } },
          },
          {
            // Elevation for the terrain relief: it never changes, so keep it longer.
            urlPattern: /^https:\/\/elevation-tiles-prod\.s3\.amazonaws\.com\/terrarium\//,
            handler: "CacheFirst",
            options: { cacheName: "terrain-tiles", expiration: { maxEntries: 200, maxAgeSeconds: 30 * 86400 } },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    host: true,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
  test: { environment: "node" },
});
