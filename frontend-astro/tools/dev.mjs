/**
 * Handles development environment setup and server
 * @module dev
 */

import { fileURLToPath } from 'url'
import { log } from './utils.mjs'
import { watchAll } from './watch.mjs'
import { buildCss } from './css.mjs'
import { buildJs } from './js.mjs'
import { copyAssets } from './assets.mjs'
import { clean } from './clean.mjs'
import path from 'path'
import open from 'open'
import { spawn } from 'child_process'
import fs from 'fs/promises'

// Get the absolute path to the project root
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// Default configuration
const DEFAULT_CONFIG = {
  port: 5174, // palimpsest project port
  host: '0.0.0.0', // listen on all interfaces
  openBrowser: true,
  startPath: '/dashboard',
  cleanBeforeBuild: true
}

/**
 * Runs initial build of all assets
 * @param {Object} [options] - Build options
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @param {boolean} [options.cleanBeforeBuild=true] - Whether to clean before build
 * @returns {Promise<void>}
 * @throws {Error} If initial build fails
 */
async function initialBuild(options = {}) {
  // Ensure options object is properly initialized with defaults
  const opts = {
    verbose: false,
    cleanBeforeBuild: true,
    ...options
  }

  log('Running initial build of all assets...', 'info')

  try {
    // Clean dist directory if needed
    if (opts.cleanBeforeBuild !== false) {
      await clean({ verbose: opts.verbose })
      log('Cleaned dist directory', 'success')
    }

    // Run all build tasks in parallel for better performance
    await Promise.all([
      buildCss({
        isDev: true,
        skipRtl: false,
        verbose: opts.verbose
      }).then(() => log('Initial CSS build completed', 'success')),

      buildJs({
        isDev: true,
        verbose: opts.verbose
      }).then(() => log('Initial JS build completed', 'success')),

      copyAssets({
        verbose: opts.verbose
      }).then(() => log('Initial assets copy completed', 'success'))
    ])

    log('Initial build completed successfully', 'success')
  } catch (error) {
    log(`Initial build failed: ${error.message}`, 'error')
    if (error.stack && opts.verbose) {
      log(`Stack trace: ${error.stack}`, 'error')
    }
    throw error
  }
}

/**
 * Starts the Astro development server
 * @param {Object} [options] - Server options
 * @param {number} [options.port=1234] - Port to run the server on
 * @param {string} [options.host="0.0.0.0"] - Host to run the server on
 * @param {boolean} [options.openBrowser=true] - Whether to open the browser
 * @param {string} [options.startPath='/dashboard'] - Path to open in the browser
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @returns {Promise<Object>} Server process and cleanup function
 * @throws {Error} If server fails to start
 */
async function startAstroServer(options = {}) {
  const port = options.port || DEFAULT_CONFIG.port
  const host = options.host || DEFAULT_CONFIG.host
  const openBrowser = options.openBrowser !== false
  const startPath = options.startPath || DEFAULT_CONFIG.startPath

  log('Starting Astro development server...', 'info')

  // Ensure config file exists
  const configPath = path.join(projectRoot, 'config/astro.config.mjs')
  try {
    await fs.access(configPath)
  } catch {
    throw new Error(`Astro config file not found: ${configPath}`)
  }

  return new Promise((resolve, reject) => {
    const child = spawn(
      'npx',
      [
        'astro',
        'dev',
        '--config',
        'config/astro.config.mjs',
        '--root',
        '.',
        '--port',
        port.toString(),
        '--host',
        host
      ],
      {
        shell: true,
        stdio: 'inherit',
        cwd: projectRoot,
        env: {
          ...process.env,
          ASTRO_TELEMETRY_DISABLED: '1', // Disable telemetry for cleaner logs
          NODE_ENV: 'development' // Set development environment
        }
      }
    )

    let serverStarted = false

    // Set a timeout to detect if server fails to start
    const startTimeout = setTimeout(() => {
      if (!serverStarted) {
        reject(new Error('Astro server failed to start within the timeout period'))
      }
    }, 30000) // 30 second timeout

    child.on('error', (error) => {
      clearTimeout(startTimeout)
      reject(new Error(`Failed to start Astro server: ${error.message}`))
    })

    // Wait a bit for the server to start, then open the URL
    setTimeout(async () => {
      try {
        serverStarted = true
        clearTimeout(startTimeout)

        const url = `http://localhost:${port}${startPath}`
        log(`Development server started at ${url}`, 'success')
        log(
          `Also available at http://${host === '0.0.0.0' ? 'your-local-ip' : host}:${port}${startPath}`,
          'success'
        )

        if (openBrowser) {
          await open(url)
          log(`Browser opened at ${url}`, 'success')
        }

        resolve({
          process: child,
          cleanup: () => {
            return new Promise((resolve) => {
              child.on('close', () => resolve())
              child.kill('SIGTERM')
            })
          }
        })
      } catch (error) {
        log(`Failed to open browser: ${error.message}`, 'error')
        // Still resolve as the server is running
        resolve({
          process: child,
          cleanup: () => {
            return new Promise((resolve) => {
              child.on('close', () => resolve())
              child.kill('SIGTERM')
            })
          }
        })
      }
    }, 3000) // Wait 3 seconds for server to be ready
  })
}

/**
 * Starts the development server and file watchers
 * @param {Object} [options] - Development options
 * @param {number} [options.port=1234] - Port to run the server on
 * @param {string} [options.host="0.0.0.0"] - Host to run the server on
 * @param {boolean} [options.openBrowser=true] - Whether to open the browser
 * @param {string} [options.startPath='/dashboard'] - Path to open in the browser
 * @param {boolean} [options.cleanBeforeBuild=true] - Whether to clean before initial build
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @returns {Promise<Function>} Cleanup function
 * @throws {Error} If development server fails to start
 */
export async function startDevServer(options = {}) {
  // Ensure options object is properly initialized with defaults
  const config = {
    ...DEFAULT_CONFIG,
    ...options
  }

  let watchCleanup = null
  let serverCleanup = null

  try {
    log('Starting development environment...', 'info')

    // Run initial build before starting watchers
    await initialBuild({
      verbose: config.verbose,
      cleanBeforeBuild: config.cleanBeforeBuild
    })

    // Start file watchers
    log('Setting up file watchers...', 'info')
    watchCleanup = await watchAll({ verbose: config.verbose })
    log('File watchers initialized successfully', 'success')

    // Start Astro dev server
    const server = await startAstroServer({
      port: config.port,
      host: config.host,
      openBrowser: config.openBrowser,
      startPath: config.startPath,
      verbose: config.verbose
    })

    serverCleanup = server.cleanup

    // Handle server process events
    server.process.on('close', async (code) => {
      if (code !== 0) {
        log(`Development server exited with code ${code}`, 'error')
      } else {
        log('Development server closed', 'info')
      }

      // Clean up watchers when Astro server closes
      if (watchCleanup) {
        log('Cleaning up file watchers...', 'info')
        try {
          await watchCleanup()
          log('File watchers cleaned up', 'success')
        } catch (error) {
          log(`Error cleaning up file watchers: ${error.message}`, 'error')
        }
      }
    })

    // Return a cleanup function
    return async () => {
      log('Shutting down development environment...', 'info')

      if (serverCleanup) {
        try {
          await serverCleanup()
          log('Development server shut down', 'success')
        } catch (error) {
          log(`Error shutting down server: ${error.message}`, 'error')
        }
      }

      if (watchCleanup) {
        try {
          await watchCleanup()
          log('File watchers cleaned up', 'success')
        } catch (error) {
          log(`Error cleaning up file watchers: ${error.message}`, 'error')
        }
      }

      log('Development environment shut down', 'success')
    }
  } catch (error) {
    log(`Development server error: ${error.message}`, 'error')

    // Clean up resources on error
    if (serverCleanup) {
      try {
        await serverCleanup()
      } catch (cleanupError) {
        log(`Error shutting down server: ${cleanupError.message}`, 'error')
      }
    }

    if (watchCleanup) {
      try {
        await watchCleanup()
      } catch (cleanupError) {
        log(`Error cleaning up file watchers: ${cleanupError.message}`, 'error')
      }
    }

    throw error
  }
}

// Handle graceful shutdown
process.on('SIGINT', async () => {
  log('Shutting down development server...', 'info')
  process.exit(0)
})

process.on('SIGTERM', async () => {
  log('Shutting down development server...', 'info')
  process.exit(0)
})

// Execute if run directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const port = parseInt(
    process.argv.find((arg) => arg.startsWith('--port='))?.split('=')[1] || DEFAULT_CONFIG.port
  )
  const host =
    process.argv.find((arg) => arg.startsWith('--host='))?.split('=')[1] || DEFAULT_CONFIG.host
  const noOpen = process.argv.includes('--no-open')
  const verbose = process.argv.includes('--verbose')
  const noClean = process.argv.includes('--no-clean')
  const startPath =
    process.argv.find((arg) => arg.startsWith('--path='))?.split('=')[1] || DEFAULT_CONFIG.startPath

  const cleanup = startDevServer({
    port,
    host,
    openBrowser: !noOpen,
    startPath,
    cleanBeforeBuild: !noClean,
    verbose
  }).catch((error) => {
    log(`Fatal error: ${error.message}`, 'error')
    process.exit(1)
  })

  // Handle cleanup on exit
  process.on('exit', async () => {
    if (cleanup && typeof cleanup === 'function') {
      await cleanup().catch(() => {})
    }
  })
}
