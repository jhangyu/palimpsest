/**
 * Runs code quality checks without applying fixes
 * @module lint
 */

import { fileURLToPath } from 'url'
import { runCommand, log } from './utils.mjs'
import path from 'path'
import fs from 'fs/promises'

// Get the absolute path to the project root
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// Define linting tasks with their commands and arguments
const tasks = {
  lockfile: {
    name: 'Package Lockfile',
    description: 'Validates package lockfile integrity',
    cmd: 'lockfile-lint',
    args: [
      '--allowed-hosts',
      'npm',
      '--allowed-schemes',
      'https:',
      '--empty-hostname',
      'false',
      '--type',
      'npm',
      '--path',
      'package-lock.json'
    ]
  },
  js: {
    name: 'JavaScript',
    description: 'Checks JavaScript code quality',
    cmd: 'eslint',
    args: [
      '--config',
      'config/eslint.config.mjs',
      '--cache',
      '--cache-location',
      '.cache/.eslintcache',
      '--report-unused-disable-directives',
      '.'
    ]
  },
  css: {
    name: 'CSS/SCSS',
    description: 'Checks CSS/SCSS code quality',
    cmd: 'stylelint',
    args: [
      '--config',
      'config/stylelint.config.mjs',
      'src/scss/**/*.scss',
      '--cache',
      '--cache-location',
      '.cache/.stylelintcache',
      '--rd'
    ]
  },
  astro: {
    name: 'Astro',
    description: 'Validates Astro templates',
    cmd: 'astro',
    args: ['--config', 'config/astro.config.mjs', 'check']
  }
}

/**
 * Verifies that required configuration files exist
 * @param {string} taskType - Type of task to verify config for
 * @returns {Promise<void>}
 * @throws {Error} If a required config file is missing
 */
async function verifyConfig(taskType) {
  if (!taskType || !tasks[taskType]) {
    return
  }

  const task = tasks[taskType]

  // Check for config files in arguments
  const configIndex = task.args.indexOf('--config')
  if (configIndex !== -1 && configIndex + 1 < task.args.length) {
    const configPath = path.join(projectRoot, task.args[configIndex + 1])
    try {
      await fs.access(configPath)
    } catch {
      throw new Error(`Config file not found for ${task.name}: ${configPath}`)
    }
  }
}

/**
 * Runs linting tasks
 * @param {string} [taskType] - Specific task to run (optional)
 * @param {Object} [options] - Linting options
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @returns {Promise<void>}
 * @throws {Error} If linting fails
 */
export async function lint(taskType, options = {}) {
  try {
    // Validate task type if provided
    if (taskType && !tasks[taskType]) {
      throw new Error(
        `Unknown task type: ${taskType}. Available types: ${Object.keys(tasks).join(', ')}`
      )
    }

    const tasksToRun = taskType ? { [taskType]: tasks[taskType] } : tasks

    // Create .cache directory if it doesn't exist
    try {
      await fs.mkdir(path.join(projectRoot, '.cache'), { recursive: true })
    } catch (error) {
      log(`Warning: Could not create cache directory: ${error.message}`, 'warning')
    }

    // Run each task
    for (const [name, task] of Object.entries(tasksToRun)) {
      log(`Running ${task.name} lint check...`, 'info')

      // Verify config files exist
      await verifyConfig(name)

      // Run the linting command
      await runCommand(task.cmd, task.args)

      if (options.verbose) {
        log(`${task.name} lint check completed with detailed output`, 'info')
      }

      log(`✓ ${task.name} passed`, 'success')
    }

    log('All lint checks passed successfully', 'success')
  } catch (error) {
    log(`Lint error: ${error.message}`, 'error')
    throw error
  }
}

// Execute if run directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const taskType = process.argv[2]
  const verbose = process.argv.includes('--verbose')

  lint(taskType, { verbose }).catch((error) => {
    log(`Fatal lint error: ${error.message}`, 'error')
    process.exit(1)
  })
}
