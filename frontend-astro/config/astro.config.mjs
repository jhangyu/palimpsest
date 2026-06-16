/*
Note this config is used in build time only. For development server src/tools/dev.mjs
*/

import { defineConfig } from 'astro/config'
import path from 'path'

// Custom Vite plugin to watch for asset changes and trigger HMR
const assetHmrPlugin = () => {
  return {
    name: 'asset-hmr-plugin',
    configureServer(server) {
      // Watch for changes in the dist directory
      const watcher = server.watcher

      // Add dist directory to the watcher
      watcher.add(path.resolve('./dist'))

      // Watch for the reload trigger files
      watcher.on('change', (filePath) => {
        if (filePath.includes('.reload-trigger') || filePath.includes('reload-')) {
          // Force reload all clients
          server.ws.send({ type: 'full-reload' })
        }
      })

      // Watch for asset changes
      watcher.on('add', (filePath) => {
        if (filePath.startsWith(path.resolve('./dist'))) {
          // Force reload all clients
          server.ws.send({ type: 'full-reload' })
        }
      })
    }
  }
}

// https://astro.build/config
export default defineConfig({
  devToolbar: { enabled: false }, // Disable the dev toolbar
  build: {
    // Example: Generate `page.html` instead of `page/index.html` during build.
    format: 'file',
    target: 'es2020'
  },

  srcDir: './src/html',
  cacheDir: './dist/pages',
  outDir: './dist/pages',
  trailingSlash: 'never',

  server: {
    host: '0.0.0.0',
    port: 5174,
    allowedHosts: ['aifeed.jhangy.us', 'airss.jhangy.us', 'localhost']
  },

  vite: {
    plugins: [assetHmrPlugin()],
    css: {
      preprocessorOptions: {
        scss: {
          quietDeps: true
        }
      }
    },
    resolve: {
      alias: {
        '@': '/src'
      }
    },
    build: {
      target: 'es2020',
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor-echarts': ['echarts/core', 'echarts/charts', 'echarts/components', 'echarts/renderers']
          }
        }
      }
    },
    server: {
      watch: {
        // Include dist folder and ensure assets are watched
        ignored: ['!**/dist/**'],
        // Add additional files/directories to watch
        additionalPaths: ['src/assets/**/*', 'dist/**/*']
      },
      // Simplified HMR configuration to avoid WebSocket errors
      hmr: true
    }
  }
})
