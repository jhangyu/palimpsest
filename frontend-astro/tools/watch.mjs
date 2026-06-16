/**
 * Handles file watching and automatic rebuilds
 * @module watch
 */

import { fileURLToPath } from 'url'
import { log } from './utils.mjs'
import chokidar from 'chokidar'
import { spawn } from 'child_process'
import path from 'path'
import fs from 'fs/promises'

// Get the absolute path to the project root
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// Check if we're on Windows
const isWindows = process.platform === 'win32'

// Define base directories to watch
const SCSS_DIR = path.join(projectRoot, 'src/scss')
const JS_DIR = path.join(projectRoot, 'src/js')
const ASSETS_DIR = path.join(projectRoot, 'src/assets')

// Define watch configurations
const WATCH_CONFIGS = [
  {
    name: 'CSS',
    dir: SCSS_DIR,
    command: 'node tools/css.mjs --dev --skip-rtl=false',
    color: 'blue',
    filter: (path) => path.endsWith('.scss'),
    debounceMs: 300,
    triggerReload: true
  },
  {
    name: 'JS',
    dir: JS_DIR,
    command: 'node tools/js.mjs --dev',
    color: 'green',
    filter: (path) => path.endsWith('.js'),
    debounceMs: 300
  },
  {
    name: 'ASSETS',
    dir: ASSETS_DIR,
    command: 'node tools/assets.mjs',
    color: 'yellow',
    filter: () => true, // Accept all files in assets directory
    // This will trigger Astro reload via the assets.mjs script
    triggerReload: true,
    debounceMs: 500
  }
]

/**
 * Verify that the directories exist
 * @param {Object} [options] - Options
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @returns {Promise<boolean>} - Whether all directories exist
 */
async function verifyDirectories(options = {}) {
  // Ensure options object is properly initialized with defaults
  const opts = {
    verbose: false,
    ...options
  }

  let allExist = true

  for (const config of WATCH_CONFIGS) {
    try {
      await fs.access(config.dir, fs.constants.F_OK)
      if (opts.verbose) {
        log(`Verified directory ${path.relative(projectRoot, config.dir)} exists`, 'info')
      }
    } catch {
      log(`Warning: Directory ${path.relative(projectRoot, config.dir)} does not exist`, 'warning')
      allExist = false
    }
  }

  return allExist
}

/**
 * Create a touch file to trigger Astro reload
 * @param {Object} [options] - Options
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @returns {Promise<void>}
 */
async function touchReloadFile(options = {}) {
  // Ensure options object is properly initialized with defaults
  const opts = {
    verbose: false,
    ...options
  }

  const reloadFilePath = path.join(projectRoot, 'dist', '.reload-trigger')
  try {
    // Ensure the directory exists
    await fs.mkdir(path.dirname(reloadFilePath), { recursive: true })
    // Update the timestamp on the file to trigger a reload
    const now = new Date()
    await fs.writeFile(reloadFilePath, `Last reload: ${now.toISOString()}`)

    if (opts.verbose) {
      log('Created reload trigger file', 'info')
    }
  } catch (error) {
    log(`Error creating reload trigger: ${error.message}`, 'error')
  }
}

/**
 * Set up file watchers for all configured directories
 * @param {Object} [options] - Watch options
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @returns {Promise<Function>} Cleanup function to close all watchers
 * @throws {Error} If watching fails
 */
export async function watchAll(options = {}) {
  // Ensure options object is properly initialized with defaults
  const opts = {
    verbose: false,
    ...options
  }

  const watchers = []

  // Verify directories first
  await verifyDirectories(opts)

  try {
    // Create a watcher for each config
    for (const config of WATCH_CONFIGS) {
      log(
        `${config.name}: Setting up watcher for ${path.relative(projectRoot, config.dir)}`,
        'info'
      )

      // Configure watcher with optimal settings
      const watcher = chokidar.watch(config.dir, {
        ignored: (path, stats) => {
          // Skip hidden files and apply custom filter
          const isHidden = /(^|\/)\.[^/.]/g.test(path)
          return isHidden || (stats && stats.isFile() && !config.filter(path))
        },
        persistent: true,
        ignoreInitial: true,

        // Use atomic writes detection
        atomic: true,

        // Configure write finish detection
        awaitWriteFinish: {
          stabilityThreshold: config.debounceMs || 300,
          pollInterval: 100
        },

        // Platform-specific optimizations
        usePolling: isWindows,
        interval: isWindows ? 500 : 1000,
        binaryInterval: isWindows ? 500 : 1000,

        // Additional options for better performance
        alwaysStat: true,
        followSymlinks: false,
        depth: 99
      })

      let isProcessing = false
      let pendingChanges = false
      let lastFilePath = null
      let debounceTimer = null

      /**
       * Run the build command for the current config
       * @param {string} filePath - Path of the changed file
       */
      const runCommand = async (filePath) => {
        // Clear any existing debounce timer
        if (debounceTimer) {
          clearTimeout(debounceTimer)
        }

        // Set a new debounce timer
        debounceTimer = setTimeout(async () => {
          lastFilePath = filePath

          if (isProcessing) {
            pendingChanges = true
            return
          }

          isProcessing = true
          const relativePath = path.relative(projectRoot, filePath)
          log(`${config.name}: Changes detected in ${relativePath}, rebuilding...`, 'info')

          try {
            const child = spawn(config.command, {
              shell: true,
              stdio: 'inherit',
              cwd: projectRoot
            })

            await new Promise((resolve, reject) => {
              child.on('close', (code) => {
                if (code === 0) {
                  log(`${config.name}: Rebuild completed`, 'success')

                  // If this config should trigger a reload, touch the reload file
                  if (config.triggerReload) {
                    touchReloadFile({ verbose: opts.verbose }).then(() => {
                      log(`${config.name}: Triggered browser reload`, 'info')
                    })
                  }

                  resolve()
                } else {
                  log(`${config.name}: Rebuild failed with code ${code}`, 'error')
                  reject(new Error(`Process exited with code ${code}`))
                }
              })

              child.on('error', (error) => {
                log(`${config.name}: Command execution error: ${error.message}`, 'error')
                reject(error)
              })
            })
          } catch (error) {
            log(`${config.name}: ${error.message}`, 'error')
          } finally {
            isProcessing = false

            // If changes occurred during processing, run again
            if (pendingChanges) {
              pendingChanges = false
              runCommand(lastFilePath)
            }
          }
        }, config.debounceMs || 300)
      }

      // Add event listeners for all relevant events
      watcher
        .on('add', (path) => {
          if (opts.verbose) {
            log(`${config.name}: File ${path} has been added`, 'info')
          }
          runCommand(path)
        })
        .on('change', (path) => {
          if (opts.verbose) {
            log(`${config.name}: File ${path} has been changed`, 'info')
          }
          runCommand(path)
        })
        .on('unlink', (path) => {
          if (opts.verbose) {
            log(`${config.name}: File ${path} has been removed`, 'info')
          }
          runCommand(path)
        })
        .on('addDir', (path) => {
          if (opts.verbose) {
            log(`${config.name}: Directory ${path} has been added`, 'info')
          }
          if (config.triggerReload) {
            touchReloadFile({ verbose: opts.verbose })
          }
        })
        .on('unlinkDir', (path) => {
          if (opts.verbose) {
            log(`${config.name}: Directory ${path} has been removed`, 'info')
          }
          if (config.triggerReload) {
            touchReloadFile({ verbose: opts.verbose })
          }
        })
        .on('error', (error) => {
          log(`${config.name}: Watcher error: ${error}`, 'error')
        })
        .on('ready', () => {
          log(`${config.name}: Initial scan complete. Ready for changes`, 'success')
        })

      log(`${config.name}: Watching ${path.relative(projectRoot, config.dir)} for changes`, 'info')
      watchers.push(watcher)
    }

    // Return a cleanup function
    return async () => {
      log('Closing all file watchers...', 'info')
      for (const watcher of watchers) {
        await watcher.close()
      }
      log('All file watchers closed', 'success')
    }
  } catch (error) {
    log(`Watch error: ${error.message}`, 'error')

    // Clean up any watchers that were created before the error
    if (watchers.length > 0) {
      log('Cleaning up watchers due to error...', 'info')
      for (const watcher of watchers) {
        await watcher.close().catch(() => {})
      }
    }

    throw error
  }
}

// Execute if run directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const verbose = process.argv.includes('--verbose')

  watchAll({ verbose }).catch((error) => {
    log(`Fatal error: ${error.message}`, 'error')
    process.exit(1)
  })
}
