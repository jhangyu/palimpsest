import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

import node from '@astrojs/node';

// https://astro.build/config/
export default defineConfig({
  output: 'static',
  devToolbar: { enabled: false },
  integrations: [react()],

  server: {
    host: '0.0.0.0',
    port: 5174,
    allowedHosts: ['aifeed.jhangy.us', 'airss.jhangy.us', 'localhost']
  },

  vite: {
    ssr: {
      noExternal: []
    },
    resolve: {
      dedupe: ['react', 'react-dom']
    },
    optimizeDeps: {
      include: ['react', 'react-dom']
    },
    server: {
      proxy: {
        '/api': 'http://localhost:8088',
        '/sites': 'http://localhost:8088',
        '/crawl': 'http://localhost:8088',
        '/rss': 'http://localhost:8088',
        '/analyze': 'http://localhost:8088'
      }
    }
  },

  adapter: node({
    mode: 'standalone'
  })
});
