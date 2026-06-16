/**
 * Handles Astro documentation build and HTML formatting
 * @module astro
 */

import { fileURLToPath } from 'url'
import { runCommand, log } from './utils.mjs'
import prettier from 'prettier'
import fs from 'fs/promises'
import path from 'path'
import { glob } from 'glob'

// Get the absolute path to the project root
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

/**
 * Formats HTML files using Prettier
 * @param {Object} [options] - Formatting options
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @returns {Promise<void>}
 */
async function formatHtmlFiles(options = {}) {
  // Ensure options object is properly initialized with defaults
  const opts = {
    verbose: false,
    ...options
  }

  try {
    const files = await glob('dist/pages/**/*.html')

    if (files.length === 0) {
      log('No HTML files found to format', 'warning', 'ASTRO')
      return
    }

    if (opts.verbose) {
      log(`Found ${files.length} HTML files to format`, 'info', 'ASTRO')
    }

    const prettierConfig = {
      // Configuration for Prettier, consistent with project standards
      parser: 'html',
      printWidth: 120,
      tabWidth: 2,
      useTabs: false,
      singleQuote: false,
      bracketSameLine: false
    }

    // Use Promise.all for concurrent file operations to enhance performance
    const formatPromises = files.map(async (file) => {
      try {
        const content = await fs.readFile(file, 'utf8')
        const formatted = await prettier.format(content, prettierConfig)
        await fs.writeFile(file, formatted)

        if (opts.verbose) {
          log(`Formatted ${path.relative(projectRoot, file)}`, 'info', 'ASTRO')
        }
      } catch (error) {
        log(`Error formatting ${file}: ${error.message}`, 'error', 'ASTRO')
        // Continue with other files
      }
    })

    await Promise.all(formatPromises)
    log(`Formatted ${files.length} HTML files`, 'success', 'ASTRO')
  } catch (error) {
    log(`HTML formatting error: ${error.message}`, 'error', 'ASTRO')
    // Don't throw as formatting is not critical
  }
}

/**
 * Builds Astro documentation pages
 * @param {Object} [options] - Build options
 * @param {boolean} [options.skipTypeCheck=false] - Whether to skip type checking
 * @param {boolean} [options.skipFormatting=false] - Whether to skip HTML formatting
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @returns {Promise<void>}
 * @throws {Error} If build fails
 */
export async function buildPages(options = {}) {
  // Ensure options object is properly initialized with defaults
  const opts = {
    skipTypeCheck: false,
    skipFormatting: false,
    verbose: false,
    ...options
  }

  try {
    const configPath = path.join(projectRoot, 'config/astro.config.mjs')

    // Ensure config file exists
    try {
      await fs.access(configPath)
    } catch {
      throw new Error(`Astro config file not found: ${configPath}`)
    }

    // Check Astro syntax and types if not skipped
    if (!opts.skipTypeCheck) {
      log('Checking Astro syntax and types...', 'info', 'ASTRO')
      await runCommand('astro', ['--config', 'config/astro.config.mjs', 'check'])
      log('Astro syntax and type check passed', 'success', 'ASTRO')
    }

    // Build documentation pages
    log('Building Astro documentation pages...', 'info', 'ASTRO')
    await runCommand('astro', ['--config', 'config/astro.config.mjs', 'build'])
    log('Astro documentation built successfully', 'success', 'ASTRO')

    // Format generated HTML if not skipped
    if (!opts.skipFormatting) {
      log('Formatting generated HTML...', 'info', 'ASTRO')
      await formatHtmlFiles(opts)
    }
  } catch (error) {
    // Log detailed error information for better debugging
    log(`Documentation build error: ${error.message}`, 'error', 'ASTRO')
    if (error.stack) {
      log(`Stack trace: ${error.stack}`, 'error', 'ASTRO')
    }
    throw error
  }
}

// Execute if run directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const skipTypeCheck = process.argv.includes('--skip-type-check')
  const skipFormatting = process.argv.includes('--skip-formatting')
  const verbose = process.argv.includes('--verbose')

  buildPages({
    skipTypeCheck,
    skipFormatting,
    verbose
  }).catch((error) => {
    log(`Fatal Astro build error: ${error.message}`, 'error', 'ASTRO')
    process.exit(1)
  })
}
