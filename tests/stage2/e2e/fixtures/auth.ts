/**
 * Re-export the storageState path for convenience.
 *
 * Test files that need the path can import from here:
 *   import { STORAGE_STATE } from '../fixtures/auth'
 */
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export const STORAGE_STATE = path.resolve(__dirname, '../.auth/session.json')
