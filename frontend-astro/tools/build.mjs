/**
 * Main build script that orchestrates the entire build process
 * @module build
 */

import { fileURLToPath } from 'url'
import { log } from './utils.mjs'
import { clean } from './clean.mjs'
import { lint } from './lint.mjs'
import { formatCode } from './prettier.mjs'
import { buildPages } from './astro.mjs'
import { copyAssets } from './assets.mjs'
import { buildCss } from './css.mjs'
import { buildJs } from './js.mjs'

// Get the absolute path to the project root
// const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

/**
 * Runs the complete build process
 * @param {Object} [options] - Build options
 * @param {boolean} [options.skipLint=false] - Whether to skip linting
 * @param {boolean} [options.skipClean=false] - Whether to skip cleaning
 * @param {boolean} [options.skipFormat=false] - Whether to skip code formatting
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @param {boolean} [options.production=true] - Whether to build for production
 * @returns {Promise<void>}
 * @throws {Error} If build fails
 */
export async function build(options = {}) {
  // Ensure options object is properly initialized with defaults
  const opts = {
    skipLint: false,
    skipClean: false,
    skipFormat: false,
    verbose: false,
    production: true,
    ...options
  }

  try {
    const buildStartTime = performance.now()
    log('Build process started', 'info')

    // Clean output directory first if not skipped
    if (!opts.skipClean) {
      await clean({ verbose: opts.verbose })
      log('Clean completed', 'success')
    } else {
      log('Skipping clean step', 'info')
    }

    // Format code with Prettier if not skipped
    if (!opts.skipFormat) {
      await formatCode(null, { verbose: opts.verbose })
      log('Code formatting completed', 'success')
    } else {
      log('Skipping code formatting step', 'info')
    }

    // Run linting if not skipped
    if (!opts.skipLint) {
      await lint(null, { verbose: opts.verbose })
      log('Lint completed', 'success')
    } else {
      log('Skipping lint step', 'info')
    }

    // Run remaining build steps in parallel for better performance
    log('Running parallel build steps...', 'info')

    const buildTasks = [
      buildCss({
        isDev: !opts.production,
        verbose: opts.verbose
      }).then(() => log('CSS built', 'success')),

      buildJs({
        isDev: !opts.production,
        verbose: opts.verbose
      }).then(() => log('JavaScript built', 'success')),

      buildPages({
        skipTypeCheck: opts.skipLint, // Skip type check if linting is skipped
        verbose: opts.verbose
      }).then(() => log('Docs built', 'success')),

      copyAssets({
        verbose: opts.verbose
      }).then(() => log('Assets copied', 'success'))
    ]

    await Promise.all(buildTasks).catch((error) => {
      throw new Error(`Build process failed during parallel execution: ${error.message}`)
    })

    const buildEndTime = performance.now()
    const totalTime = ((buildEndTime - buildStartTime) / 1000).toFixed(2)
    log(`✨ Build completed in ${totalTime}s`, 'success')
  } catch (error) {
    log('❌ Build process failed!', 'error')
    log(error.message, 'error')
    if (error.stack && opts.verbose) {
      log(`Stack trace: ${error.stack}`, 'error')
    }
    throw error
  }
}

// Execute build if script is run directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const skipLint = process.argv.includes('--skip-lint')
  const skipClean = process.argv.includes('--skip-clean')
  const skipFormat = process.argv.includes('--skip-format')
  const verbose = process.argv.includes('--verbose')
  const dev = process.argv.includes('--dev')

  build({
    skipLint,
    skipClean,
    skipFormat,
    verbose,
    production: !dev
  }).catch(() => {
    process.exit(1)
  })
}
