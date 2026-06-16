/**
 * Runs code quality checks and attempts to fix issues automatically
 * @module fixlint
 */

import { fileURLToPath } from 'url'
import { runCommand, log } from './utils.mjs'
import path from 'path'
import fs from 'fs/promises'

// Get the absolute path to the project root
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// Configuration for linting tasks
const CONFIG = {
  tasks: {
    lock: {
      name: 'Lockfile',
      description: 'Package lockfile validation',
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
      name: 'ESLint',
      description: 'JavaScript lints fixes',
      cmd: 'eslint',
      args: [
        '--config',
        'config/eslint.config.mjs',
        '--cache',
        '--cache-location',
        '.cache/.eslintcache',
        '--report-unused-disable-directives',
        '--fix',
        '.'
      ]
    },
    css: {
      name: 'StyleLint',
      description: 'SCSS/CSS style lints fixes',
      cmd: 'stylelint',
      args: [
        'src/scss/**/*.scss',
        '--config',
        'config/stylelint.config.mjs',
        '--cache',
        '--cache-location',
        '.cache/.stylelintcache',
        '--fix',
        '--rd'
      ]
    },
    astro: {
      name: 'Astro',
      description: 'Astro template validation',
      cmd: 'astro',
      args: ['--config', 'config/astro.config.mjs', 'check']
    }
  },
  messages: {
    start: '====== Running {task} ======',
    complete: '🎉 {task} completed successfully!',
    error: '❌ Fix process failed'
  }
}

/**
 * Verifies that required configuration files exist
 * @param {string} taskType - Type of task to verify config for
 * @returns {Promise<void>}
 * @throws {Error} If a required config file is missing
 */
async function verifyConfig(taskType) {
  if (!taskType || !CONFIG.tasks[taskType]) {
    return
  }

  const task = CONFIG.tasks[taskType]

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
 * Gets lint steps for a specific task type
 * @param {string} taskType - Type of task to get steps for
 * @returns {Array} Array of task objects
 * @throws {Error} If task type is invalid
 */
function getStepsForTaskType(taskType) {
  if (taskType && !CONFIG.tasks[taskType]) {
    throw new Error(
      `Unknown task type: ${taskType}. Available types: ${Object.keys(CONFIG.tasks).join(', ')}`
    )
  }

  const selectedTasks = taskType ? [CONFIG.tasks[taskType]] : Object.values(CONFIG.tasks)
  return selectedTasks.map((task) => ({
    name: `${task.name} Fix`,
    description: task.description,
    fn: async () => {
      await runCommand(task.cmd, task.args)
      log(`✅ ${task.description} complete`, 'success')
    }
  }))
}

/**
 * Runs linting fixes
 * @param {string} [taskType] - Specific task to run (optional)
 * @param {Object} [options] - Fix options
 * @param {boolean} [options.verbose=false] - Whether to log verbose output
 * @returns {Promise<void>}
 * @throws {Error} If fixes fail
 */
export async function fixlint(taskType, options = {}) {
  // Ensure options object is properly initialized with defaults
  const opts = {
    verbose: false,
    ...options
  }

  try {
    // Create .cache directory if it doesn't exist
    try {
      await fs.mkdir(path.join(projectRoot, '.cache'), { recursive: true })
    } catch (error) {
      log(`Warning: Could not create cache directory: ${error.message}`, 'warning')
    }

    // Verify config files exist
    if (taskType) {
      await verifyConfig(taskType)
    } else {
      // Verify all configs
      for (const type of Object.keys(CONFIG.tasks)) {
        await verifyConfig(type)
      }
    }

    const stepsToRun = getStepsForTaskType(taskType)
    const taskDescription = taskType ? CONFIG.tasks[taskType].description : 'all available fixes'

    log(CONFIG.messages.start.replace('{task}', taskDescription), 'info')

    for (let i = 0; i < stepsToRun.length; i++) {
      const step = stepsToRun[i]
      const stepNumber = `[${i + 1}/${stepsToRun.length}]`

      try {
        if (opts.verbose) {
          log(`${stepNumber} Running ${step.name}...`, 'info')
        }

        await step.fn()
        log(`${stepNumber} ${step.description} applied`, 'success')
      } catch (error) {
        throw new Error(`${step.name} failed: ${error.message}`)
      }
    }

    log(CONFIG.messages.complete.replace('{task}', taskDescription), 'success')
  } catch (error) {
    log(CONFIG.messages.error, 'error')
    log(error.message, 'error')
    throw error
  }
}

// Execute if run directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const taskType = process.argv[2]
  const verbose = process.argv.includes('--verbose')

  fixlint(taskType, { verbose }).catch((error) => {
    log(`Fatal fixlint error: ${error.message}`, 'error')
    process.exit(1)
  })
}
