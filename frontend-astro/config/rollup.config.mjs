import { readFileSync } from 'fs'
import { URL } from 'url'
import resolve from '@rollup/plugin-node-resolve'
import commonjs from '@rollup/plugin-commonjs'
import terser from '@rollup/plugin-terser'

// Read package.json from root directory
const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'))

const year = new Date().getFullYear()
const banner = `/*!
 * Astero Admin v${pkg.version} (${pkg.homepage})
 * Copyright 2025-${year} ${pkg.author}
 * Licensed under MIT (https://github.com/asterodigital/bootstrap-admin-template/blob/master/LICENSE)
 */`

export default {
  input: 'src/js/main.js',
  output: [
    {
      file: 'dist/js/main.js',
      format: 'iife',
      name: 'AsteroAdmin',
      banner,
      sourcemap: true,
      globals: {
        'bootstrap': 'bootstrap',
        'simplebar': 'SimpleBar'
      }
    },
    {
      file: 'dist/js/main.min.js',
      format: 'iife',
      name: 'AsteroAdmin',
      banner,
      sourcemap: true,
      plugins: [terser()],
      globals: {
        'bootstrap': 'bootstrap',
        'simplebar': 'SimpleBar'
      }
    }
  ],
  plugins: [
    // Resolve node_modules dependencies
    resolve({
      browser: true,
      preferBuiltins: false,
      mainFields: ['module', 'main', 'browser']
    }),
    // Convert CommonJS modules to ES6
    commonjs({
      include: 'node_modules/**'
    })
  ]
}
