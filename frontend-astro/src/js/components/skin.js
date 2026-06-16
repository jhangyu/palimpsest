/**
 * Skin Management System
 *
 * This module handles dynamic styling updates based on theme-specific CSS variables.
 * It includes accordion icon colors and other skin-related functionality.
 */

/**
 * Generate SVG data URL for accordion chevron icon with specified color
 * @param {string} color - The color for the SVG stroke (e.g., '#212529', 'rgb(33, 37, 41)')
 * @returns {string} - SVG data URL string
 */
function generateSkinChevronIconSVG(color) {
  // URL encode the color to handle special characters like # and spaces
  const encodedColor = encodeURIComponent(color)

  return `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='${encodedColor}' stroke-width='1' stroke-linecap='round' stroke-linejoin='round'%3e%3cpath d='M2 5L8 11L14 5'/%3e%3c/svg%3e")`
}

/**
 * Create 20% darker RGB values from existing RGB CSS variables
 * @param {string} rgbString - RGB values as string (e.g., "117, 51, 249")
 * @returns {string} - Darker RGB values as string
 */
function createDarkerRGB(rgbString) {
  if (!rgbString || !rgbString.trim()) {
    return rgbString
  }

  try {
    // Parse the RGB values
    const rgbValues = rgbString.split(',').map((val) => parseInt(val.trim(), 10))

    if (rgbValues.length !== 3 || rgbValues.some((val) => isNaN(val))) {
      return rgbString // Return original if parsing fails
    }

    // Make each component 20% darker (multiply by 0.8)
    const darkerValues = rgbValues.map((val) => Math.round(val * 0.8))

    return darkerValues.join(', ')
  } catch (error) {
    console.warn('Error creating darker RGB values:', error)
    return rgbString // Return original on error
  }
}

/**
 * Update skin RGB darker variables
 * Reads --bs-primary-rgb and --bs-secondary-rgb and creates 20% darker versions
 */
export function updateSkinRGBDarker() {
  const documentElement = document.documentElement
  const computedStyles = window.getComputedStyle(documentElement)

  // Read the existing RGB values
  const primaryRGB = computedStyles.getPropertyValue('--bs-primary-rgb').trim()
  const secondaryRGB = computedStyles.getPropertyValue('--bs-secondary-rgb').trim()

  // Create darker versions (20% darker)
  const primaryRGBDarker = createDarkerRGB(primaryRGB)
  const secondaryRGBDarker = createDarkerRGB(secondaryRGB)

  // Set the new CSS variables
  documentElement.style.setProperty('--bs-primary-rgb-darker', primaryRGBDarker)
  documentElement.style.setProperty('--bs-secondary-rgb-darker', secondaryRGBDarker)
}

/**
 * Update form switch background with primary color mixed with white
 * Reads --bs-primary and creates SVG with 50% primary + 50% white color
 */
export function updateSkinFormSwitchBg() {
  const documentElement = document.documentElement
  const computedStyles = window.getComputedStyle(documentElement)

  // Read the primary color
  const primaryColor = computedStyles.getPropertyValue('--bs-primary').trim()

  if (!primaryColor) {
    return // Exit if no primary color found
  }

  // Create color-mix: 50% primary + 50% white
  const mixedColor = `color-mix(in srgb, ${primaryColor} 50%, white)`

  // URL encode the color for SVG
  const encodedColor = encodeURIComponent(mixedColor)

  // Create the SVG data URL
  const svgDataURL = `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='-4 -4 8 8'%3e%3ccircle r='3' fill='${encodedColor}'/%3e%3c/svg%3e")`

  // Set the CSS variable
  documentElement.style.setProperty('--skin-form-switch-bg', svgDataURL)
}

/**
 * Update accordion icon colors based on current skin's CSS variables
 * This function reads "pointer" variables from the current skin CSS that tell it
 * which existing CSS variables to use as color sources for the accordion icons
 */
export function updateSkinAccordionIcons() {
  const documentElement = document.documentElement
  const computedStyles = window.getComputedStyle(documentElement)

  // Read the pointer variables that tell us which CSS variables to use for colors
  // These are defined in skin CSS files (e.g., grape.css, teal.css)
  const defaultIconColorSource = computedStyles
    .getPropertyValue('--skin-accordion-default-icon-color-source')
    .trim()
  const activeIconColorSource = computedStyles
    .getPropertyValue('--skin-accordion-active-icon-color-source')
    .trim()

  let defaultIconColor = ''
  let activeIconColor = ''

  // If pointer variables are defined, use them to get the actual color values
  if (defaultIconColorSource) {
    // Remove any quotes that might be in the CSS variable value
    const cleanSource = defaultIconColorSource.replace(/['"]/g, '')
    defaultIconColor = computedStyles.getPropertyValue(cleanSource).trim()
  }

  if (activeIconColorSource) {
    // Remove any quotes that might be in the CSS variable value
    const cleanSource = activeIconColorSource.replace(/['"]/g, '')
    activeIconColor = computedStyles.getPropertyValue(cleanSource).trim()
  }

  // Fallback colors if pointer variables or their targets are not defined
  if (!defaultIconColor) {
    const currentTheme = documentElement.getAttribute('data-bs-theme')
    if (currentTheme === 'dark') {
      defaultIconColor = '#dee2e6' // Default dark theme body color
    } else {
      defaultIconColor = '#212529' // Default light theme body color
    }
  }

  if (!activeIconColor) {
    // Try to get Bootstrap's primary color as fallback
    activeIconColor = computedStyles.getPropertyValue('--bs-primary').trim() || '#0d6efd'
  }

  // Generate SVG data URLs with the resolved colors
  const defaultIconSVG = generateSkinChevronIconSVG(defaultIconColor)
  const activeIconSVG = generateSkinChevronIconSVG(activeIconColor)

  // Set the CSS variables that control the accordion button icons
  documentElement.style.setProperty('--skin-accordion-btn-icon', defaultIconSVG)
  documentElement.style.setProperty('--skin-accordion-btn-active-icon', activeIconSVG)
}

/**
 * Initialize skin theme observer to watch for theme changes
 * When data-bs-theme attribute changes, update skin elements accordingly
 */
export function initSkinThemeObserver() {
  const observer = new window.MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'attributes' && mutation.attributeName === 'data-bs-theme') {
        // Theme changed, update skin elements with new theme
        updateSkinAccordionIcons()
        updateSkinRGBDarker()
        updateSkinFormSwitchBg()
      }
    })
  })

  // Watch for attribute changes on the document element
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-bs-theme']
  })
}

/**
 * Initialize the skin system
 * Call this function after DOM is loaded and CSS is parsed
 */
export function initSkin() {
  updateSkinAccordionIcons()
  updateSkinRGBDarker()
  updateSkinFormSwitchBg()
  initSkinThemeObserver()
}

/**
 * Update all skin elements
 * This function can be extended to update other skin-related elements
 */
export function updateSkin() {
  updateSkinAccordionIcons()
  updateSkinRGBDarker()
  updateSkinFormSwitchBg()
  // Add other skin update functions here in the future
}
