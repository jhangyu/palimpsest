/**
 * Cleans build artifacts and output directories
 * @module clean
 */

import { fileURLToPath } from 'url'
import { log } from './utils.mjs'
import fs from 'node:fs/promises'
import path from 'node:path'

// Get the absolute path to the project root
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

/**
 * Removes the dist directory and other build artifacts
 * @param {Object} [options] - Cleaning options
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @param {boolean} [options.cleanCache=false] - Whether to clean cache directory
 * @returns {Promise<void>}
 * @throws {Error} If cleanup fails
 */
export async function clean(options = {}) {
  // Ensure options object is properly initialized with defaults
  const opts = {
    verbose: false,
    cleanCache: false,
    ...options
  }

  const distPath = path.join(projectRoot, 'dist')
  const cachePath = path.join(projectRoot, '.cache')

  try {
    // Check if dist directory exists before attempting to remove
    const distExists = await fs
      .access(distPath)
      .then(() => true)
      .catch(() => false)
    if (distExists) {
      await fs.rm(distPath, { recursive: true, force: true })
      log('Cleaned dist directory', 'success')
    } else if (opts.verbose) {
      log('Dist directory does not exist, skipping', 'info')
    }

    // Optionally clean cache directory
    if (opts.cleanCache) {
      const cacheExists = await fs
        .access(cachePath)
        .then(() => true)
        .catch(() => false)
      if (cacheExists) {
        await fs.rm(cachePath, { recursive: true, force: true })
        log('Cleaned cache directory', 'success')
      } else if (opts.verbose) {
        log('Cache directory does not exist, skipping', 'info')
      }
    }
  } catch (error) {
    log(`Cleanup error: ${error.message}`, 'error')
    throw error
  }
}

// Execute if run directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const cleanCache = process.argv.includes('--clean-cache')
  const verbose = process.argv.includes('--verbose')

  clean({ cleanCache, verbose }).catch((error) => {
    log(`Fatal cleanup error: ${error.message}`, 'error')
    process.exit(1)
  })
}
