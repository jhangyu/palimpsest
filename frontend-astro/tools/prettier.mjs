/**
 * Handles HTML and Astro files formatting with Prettier
 * @module prettier
 */

import { fileURLToPath } from 'url'
import { log } from './utils.mjs'
import path from 'path'
import fs from 'fs/promises'
import { glob } from 'glob'

// Get the absolute path to the project root
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

/**
 * Formats HTML and Astro files using Prettier
 * @param {string|null} [targetPath=null] - Specific path to format, defaults to src/html directory
 * @returns {Promise<void>}
 * @throws {Error} If formatting fails
 */
export async function formatCode(targetPath = null) {
  // Default to src/html directory if no target path provided
  let pathToFormat = targetPath || path.join(projectRoot, 'src', 'html')
  const relativePath = path.relative(projectRoot, pathToFormat)

  // Ensure we're only formatting within src/html
  if (!relativePath.startsWith('src/html') && !relativePath.startsWith('src\\html')) {
    log(
      `Warning: Formatting is restricted to src/html directory. Adjusting target path.`,
      'warn',
      'PRETTIER'
    )
    pathToFormat = path.join(projectRoot, 'src', 'html')
  }

  log(`Formatting HTML and Astro files: ${relativePath}`, 'info', 'PRETTIER')

  try {
    // Dynamically import prettier and the astro plugin
    const prettier = await import('prettier')

    // Try to load the Astro plugin
    let astroPlugin
    try {
      astroPlugin = await import('prettier-plugin-astro')
    } catch (pluginError) {
      log(
        `Warning: Could not load prettier-plugin-astro: ${pluginError.message}`,
        'warn',
        'PRETTIER'
      )
    }

    // Import the Prettier config directly
    const configPath = path.join(projectRoot, 'config', 'prettier.config.mjs')
    let prettierConfig

    try {
      // Try to import the config file directly
      const configModule = await import(`file://${configPath}`)
      prettierConfig = configModule.default
    } catch (configError) {
      log(
        `Could not load Prettier config from ${configPath}, falling back to resolveConfig: ${configError.message}`,
        'warn',
        'PRETTIER'
      )
      // Fall back to resolveConfig if direct import fails
      prettierConfig = await prettier.resolveConfig(projectRoot)
    }

    // Ensure the Astro plugin is included
    if (!prettierConfig.plugins || !prettierConfig.plugins.includes('prettier-plugin-astro')) {
      prettierConfig.plugins = [...(prettierConfig.plugins || []), 'prettier-plugin-astro']
    }

    // Add parser overrides for Astro files if not already present
    if (!prettierConfig.overrides || !prettierConfig.overrides.some((o) => o.files === '*.astro')) {
      prettierConfig.overrides = [
        ...(prettierConfig.overrides || []),
        {
          files: '*.astro',
          options: {
            parser: 'astro'
          }
        }
      ]
    }

    // Find all files to format - only HTML and Astro files in src/html
    const files = await glob(`${pathToFormat}/**/*.{html,astro}`, {
      ignore: [
        '**/node_modules/**',
        '**/dist/**',
        '**/src/scss/**',
        '**/*.scss',
        // Skip all JavaScript files
        '**/*.js',
        '**/*.jsx',
        '**/*.ts',
        '**/*.tsx',
        '**/*.mjs',
        '**/*.cjs'
      ]
    })

    log(`Found ${files.length} files to format`, 'info', 'PRETTIER')

    // Create a Prettier instance with the Astro plugin explicitly loaded
    const options = {
      ...prettierConfig,
      plugins: astroPlugin ? [astroPlugin] : prettierConfig.plugins
    }

    // Track problematic files
    const problemFiles = []
    const knownProblematicFiles = [
      'component-preview.astro' // Add known problematic files here
    ]

    // Format files
    let formattedCount = 0
    let unchangedCount = 0
    let skippedCount = 0

    for (const file of files) {
      // Skip known problematic files
      const fileName = path.basename(file)
      if (knownProblematicFiles.includes(fileName)) {
        skippedCount++
        continue
      }

      try {
        const fileContent = await fs.readFile(file, 'utf8')
        const formattedContent = await prettier.format(fileContent, {
          ...options,
          filepath: file
        })

        if (fileContent !== formattedContent) {
          await fs.writeFile(file, formattedContent, 'utf8')
          formattedCount++
        } else {
          unchangedCount++
        }
      } catch (formatError) {
        const errorMessage = `Error formatting ${path.relative(projectRoot, file)}: ${formatError.message}`
        log(errorMessage, 'error', 'PRETTIER')
        problemFiles.push(file)
        skippedCount++
      }
    }

    log(
      `Processed ${files.length} files: ${formattedCount} formatted, ${unchangedCount} unchanged, ${skippedCount} skipped`,
      'info',
      'PRETTIER'
    )

    if (problemFiles.length > 0) {
      const fileList = problemFiles
        .map((file) => `  - ${path.relative(projectRoot, file)}`)
        .join('\n')
      log(
        `The following ${problemFiles.length} files were skipped due to errors:\n${fileList}`,
        'warn',
        'PRETTIER'
      )
    }

    log(`HTML formatting completed successfully`, 'success', 'PRETTIER')
  } catch (error) {
    log(`HTML formatting failed: ${error.message}`, 'error', 'PRETTIER')
    throw error
  }
}

// Execute if run directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const targetPath = process.argv[2] || null
  formatCode(targetPath).catch((error) => {
    log(`Fatal error: ${error.message}`, 'error', 'PRETTIER')
    process.exit(1)
  })
}
