/**
 * Get the path prefix based on environment
 * @param {string} path - The path to prefix
 * @returns {string} The prefixed path
 */
export function getPathPrefix(path) {
  const isDev = window.location.port === '1234'
  return isDev ? `${path}` : `/pages${path}`
}

/**
 * Get the asset prefix based on environment
 * @param {string} path - The path to prefix
 * @returns {string} The prefixed asset path
 */
export function getAssetPrefix(path) {
  const isDev = window.location.port === '1234'
  return isDev ? `/dist${path}` : `${path}`
}
