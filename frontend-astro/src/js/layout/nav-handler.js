/**
 * Initializes the sidebar navigation functionality.
 * Handles submenu toggling and menu state management.
 *
 * Key features:
 * - Uses event delegation for efficient click handling
 * - Manages submenu open/close states
 * - Handles chevron rotation animations
 * - Maintains menu hierarchy (closes sibling menus)
 */
export function initNavigation() {
  const navTree = document.querySelector(".nav-tree")

  if (!navTree) {
    // console.warn("Navigation tree element '.nav-tree' not found.")
    return
  }

  navTree.addEventListener("click", (event) => {
    const link = event.target.closest(".nav-link")
    if (!link) return

    const navItem = link.closest(".nav-item")
    // Only process clicks on menu items with submenus
    if (!navItem?.classList.contains("has-submenu")) return

    event.preventDefault()

    const isCurrentlyOpen = navItem.classList.contains("open")
    const isTopLevelItem = !navItem.closest(".submenu")

    // If opening a menu, close its siblings first
    if (!isCurrentlyOpen) {
      // Find and close other open menus at the same level
      const parentList = navItem.closest(isTopLevelItem ? ".nav-tree" : ".submenu")
      const siblingSubmenus = parentList.querySelectorAll(":scope > .nav-item.has-submenu.open")

      siblingSubmenus.forEach((sibling) => {
        if (sibling !== navItem) {
          sibling.classList.remove("open")
          const chevron = sibling.querySelector(".bi-chevron-right")
          if (chevron) chevron.style.transform = ""
        }
      })
    }

    // Toggle the clicked menu's state
    navItem.classList.toggle("open")

    // Update chevron rotation
    const chevronIcon = link.querySelector(".bi-chevron-right")
    if (chevronIcon) {
      chevronIcon.style.transform = navItem.classList.contains("open") ? "rotate(90deg)" : ""
    }
  })
}
