import * as bootstrap from 'bootstrap/dist/js/bootstrap.esm.js'
import { darkMode } from './layout/dark-mode.js'
import { initSidebar, cleanupSidebar } from './layout/sidebar-handler.js'
import { initSidebarMini, cleanupSidebarMini } from './layout/sidebar-mini-handler.js'
import { initNavigation, cleanupNavigation } from './layout/nav-handler.js'
import { initPasswordWrapper } from './components/password.js'
import { initSkin, updateSkin, cleanupSkin } from './components/skin.js'

// Expose bootstrap globally for inline scripts
window.bootstrap = bootstrap

// Create the theme module
const PalimpsestAdmin = (function () {
  let initialized = false

  // Initialize Bootstrap components
  function initBootstrap() {
    // Enable tooltips everywhere
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
    Array.from(tooltipTriggerList).forEach((tooltipTriggerEl) => {
      new bootstrap.Tooltip(tooltipTriggerEl)
    })

    // Enable popovers everywhere
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]')
    Array.from(popoverTriggerList).forEach((popoverTriggerEl) => {
      new bootstrap.Popover(popoverTriggerEl)
    })
  }

  function cleanupAll() {
    // Dispose all Bootstrap Tooltip instances
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
      bootstrap.Tooltip.getInstance(el)?.dispose()
    })
    // Dispose all Bootstrap Popover instances
    document.querySelectorAll('[data-bs-toggle="popover"]').forEach((el) => {
      bootstrap.Popover.getInstance(el)?.dispose()
    })
    cleanupSidebar()
    cleanupSidebarMini()
    cleanupNavigation()
    cleanupSkin()
  }

  function initializeAll() {
    try {
      cleanupAll()
      darkMode()
      initSidebar()
      initSidebarMini()
      initNavigation()
      initPasswordWrapper()
      initBootstrap()
      initSkin()
      initialized = true
    } catch (error) {
      console.error('Error during initialization:', error)
    }
  }

  // Public API
  return {
    init: initializeAll,
    cleanup: cleanupAll,
    isInitialized: () => initialized,
    updateSkin: updateSkin
  }
})()

// Auto-initialize on first load and after View Transitions navigation
if (typeof document !== 'undefined') {
  // Initial page load: run as early as possible
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', PalimpsestAdmin.init)
  } else {
    PalimpsestAdmin.init()
  }
  // View Transition navigation only (does NOT fire on initial load)
  document.addEventListener('astro:after-swap', PalimpsestAdmin.init)
  // Cleanup before DOM swap to prevent listener leaks
  document.addEventListener('astro:before-swap', PalimpsestAdmin.cleanup)
}

export default PalimpsestAdmin
