import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      strategies: 'generateSW',
      registerType: 'prompt',
      injectRegister: false,
      includeAssets: ['favicon.ico', 'app-icon.png'],
      manifest: {
        id: '/',
        name: '鳴潮対決カウンター',
        short_name: '鳴潮対決',
        lang: 'ja',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        theme_color: '#070b12',
        background_color: '#070b12',
        // Dedicated install icons will replace this existing icon in step 3.
        icons: [
          {
            src: '/app-icon.png',
            sizes: '256x256',
            type: 'image/png',
            purpose: 'any',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{html,js,css,wasm,png,ico,svg}'],
        navigateFallback: '/index.html',
        navigateFallbackAllowlist: [/^\/$/],
        cleanupOutdatedCaches: true,
        skipWaiting: false,
      },
      devOptions: { enabled: false },
    }),
  ],
  server: { host: '127.0.0.1', port: 1421, strictPort: true },
});
