/**
 * Returns the correct asset path based on environment
 * @param {string} path - The asset path without leading slash
 * @returns {string} - The correct path for the current environment
 */
function getAssetPrefix(path) {
  const isDev = import.meta.env.DEV
  return isDev ? `/dist${path}` : `${path}`
}

function getPathPrefix(path) {
  const isDev = import.meta.env.DEV
  return isDev ? `${path}` : `/pages${path}`
}

export { getAssetPrefix, getPathPrefix }
