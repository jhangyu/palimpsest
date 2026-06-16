/**
 * Standalone script to format HTML and Astro files with Prettier
 * @module format
 */

import { fileURLToPath } from 'url'
import { log } from './utils.mjs'
import { formatCode } from './prettier.mjs'
import path from 'path'

// Execute if run directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const targetPath = process.argv[2] && !process.argv[2].startsWith('--') ? process.argv[2] : null

  // Ensure target path is within src/html if specified
  let formattingPath = targetPath
  if (targetPath) {
    const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
    const relativePath = path.relative(projectRoot, path.resolve(projectRoot, targetPath))

    if (!relativePath.startsWith('src/html') && !relativePath.startsWith('src\\html')) {
      log(`Warning: Formatting is restricted to src/html directory. Adjusting target path.`, 'warn')
      formattingPath = path.join(projectRoot, 'src', 'html')
    }
  }

  log(`Starting HTML and Astro files formatting...`, 'info')

  formatCode(formattingPath)
    .then(() => {
      log(`HTML formatting completed successfully`, 'success')
    })
    .catch((error) => {
      log(`HTML formatting failed: ${error.message}`, 'error')
      process.exit(1)
    })
}
