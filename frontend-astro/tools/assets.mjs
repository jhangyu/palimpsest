/**
 * Copies static assets to distribution directory
 * @module assets
 */

import { fileURLToPath } from 'url'
import { runCommand, log } from './utils.mjs'
import fs from 'fs/promises'
import path from 'path'

// Get the absolute path to the project root
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

/**
 * Creates files to trigger browser reload
 * @param {Object} [options] - Options for reload trigger
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @returns {Promise<void>}
 */
async function touchReloadFile(options = {}) {
  // Ensure options object is properly initialized with defaults
  const opts = {
    verbose: false,
    ...options
  }

  try {
    // Create multiple reload triggers to ensure detection
    const triggerFiles = [
      path.join(projectRoot, 'dist', '.reload-trigger'),
      path.join(projectRoot, 'dist', 'pages', '.reload-trigger'),
      path.join(projectRoot, 'dist', 'css', '.reload-trigger')
    ]

    const now = new Date()
    const content = `Last reload: ${now.toISOString()}`

    for (const filePath of triggerFiles) {
      // Ensure the directory exists
      await fs.mkdir(path.dirname(filePath), { recursive: true })
      // Update the timestamp on the file to trigger a reload
      await fs.writeFile(filePath, content)
    }

    // Create a new random JS file to force a reload
    const randomId = Math.random().toString(36).substring(2, 15)
    const jsReloadPath = path.join(projectRoot, 'dist', `reload-${randomId}.js`)
    await fs.writeFile(jsReloadPath, `// Reload trigger: ${now.toISOString()}`)

    if (opts.verbose) {
      log('Created reload trigger files', 'info', 'ASSETS')
    }

    // Clean up old reload files (keep only the last 5)
    const reloadDir = path.join(projectRoot, 'dist')
    try {
      const files = await fs.readdir(reloadDir)
      const oldReloadFiles = files.filter((f) => f.startsWith('reload-') && f.endsWith('.js'))

      if (oldReloadFiles.length > 5) {
        // Sort by creation time and remove the oldest ones
        const fileStats = await Promise.all(
          oldReloadFiles.map(async (file) => {
            const filePath = path.join(reloadDir, file)
            const stats = await fs.stat(filePath)
            return { path: filePath, mtime: stats.mtime.getTime() }
          })
        )

        const filesToRemove = fileStats
          .sort((a, b) => a.mtime - b.mtime)
          .slice(0, oldReloadFiles.length - 5)
          .map((file) => file.path)

        for (const file of filesToRemove) {
          await fs.unlink(file).catch(() => {})
        }
      }
    } catch (error) {
      // Non-fatal error, just log it
      log(`Warning: Error cleaning up old reload files: ${error.message}`, 'warning', 'ASSETS')
    }
  } catch (error) {
    log(`Error creating reload trigger: ${error.message}`, 'error', 'ASSETS')
    // Don't throw this error as it's not critical
  }
}

/**
 * Copies assets from source to distribution directory
 * @param {Object} [options] - Options for asset copying
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @param {boolean} [options.triggerReload=true] - Whether to trigger browser reload
 * @returns {Promise<void>}
 * @throws {Error} If asset copying fails
 */
export async function copyAssets(options = {}) {
  // Ensure options object is properly initialized with defaults
  const opts = {
    verbose: false,
    triggerReload: true,
    ...options
  }

  try {
    log('Copying assets...', 'info', 'ASSETS')

    // Ensure the config file exists
    const configPath = path.join(projectRoot, 'config/assets.config.mjs')
    try {
      await fs.access(configPath)
    } catch {
      throw new Error(`Assets config file not found: ${configPath}`)
    }

    await runCommand('node', [configPath])
    log('Assets copied successfully', 'success', 'ASSETS')

    // Touch the reload file to trigger a browser refresh if needed
    if (opts.triggerReload) {
      await touchReloadFile(opts)
      log('Triggered browser reload', 'info', 'ASSETS')
    }
  } catch (error) {
    log(`Asset copy error: ${error.message}`, 'error', 'ASSETS')
    throw error
  }
}

// Execute if run directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const verbose = process.argv.includes('--verbose')
  const noReload = process.argv.includes('--no-reload')

  copyAssets({
    verbose,
    triggerReload: !noReload
  }).catch((error) => {
    log(`Fatal asset copy error: ${error.message}`, 'error', 'ASSETS')
    process.exit(1)
  })
}
