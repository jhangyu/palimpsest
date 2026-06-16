// sidebar-mini handling functionality
export const initSidebarMini = () => {
  const sidebar = document.querySelector(".sidebar")
  const mainContent = document.querySelector(".main-content")
  const sidebarMiniToggle = document.getElementById("toggle-mini-button")

  const toggleSidebarMini = () => {
    // Toggle the sidebar-mini class
    sidebar?.classList.toggle("sidebar-mini")

    // remove open clas from sidebar when toggle mini button
    sidebar.classList.remove("open")
    mainContent?.classList.remove("expanded-mini")

    // Save only the sidebar mini state to localStorage
    localStorage.setItem(
      "sidebar-mini",
      sidebar?.classList.contains("sidebar-mini") ? "true" : "false"
    )
    // Removed localStorage saving for sidebar state

    // Toggle icon classes between ri-contract-left-line and ri-contract-right-line
    updateIcon()
  }

  const updateIcon = () => {
    const icon = sidebarMiniToggle?.querySelector("i")
    if (icon) {
      if (sidebar.classList.contains("sidebar-mini")) {
        icon.classList.remove("ri-arrow-left-double-line")
        icon.classList.add("ri-arrow-right-double-line")
      } else {
        icon.classList.remove("ri-arrow-right-double-line")
        icon.classList.add("ri-arrow-left-double-line")
      }
    }
  }

  sidebarMiniToggle?.addEventListener("click", toggleSidebarMini)

  // Hover event to toggle 'expanded' class when .sidebar-mini is present
  sidebar?.addEventListener("mouseenter", () => {
    if (sidebar.classList.contains("sidebar-mini")) {
      sidebar.classList.add("open")
      // check current target is toggle-mini than stop the function
      mainContent?.classList.toggle("expanded-mini")
      // Find .nav-tree and check for .nav-item .has-submenu .active, then add .open
      const navItems = document.querySelectorAll(".nav-tree .nav-item.has-submenu.active")
      navItems.forEach((item) => {
        item.classList.add("open")
      })
    }
  })

  sidebar?.addEventListener("mouseleave", () => {
    if (sidebar.classList.contains("sidebar-mini")) {
      sidebar.classList.remove("open")
      mainContent?.classList.toggle("expanded-mini")
      // Find .nav-tree and check for .has-submenu.open, then remove .open
      const navItems = document.querySelectorAll(".nav-tree .has-submenu.open")
      navItems.forEach((item) => {
        item.classList.remove("open")
        // Find .ri-arrow-right-s-line and remove its inline transform style
        const chevron = item.querySelector(".ri-arrow-right-s-line")
        if (chevron) {
          chevron.style.transform = "" // Reset the 'transform' style
        }
      })
    }
  })
}
