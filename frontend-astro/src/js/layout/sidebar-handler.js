// Sidebar handling functionality
export const initSidebar = () => {
  const sidebarToggle = document.getElementById("sidebar-toggle")
  const sidebar = document.querySelector(".sidebar")
  const mainContent = document.querySelector(".main-content")
  const overlay = document.querySelector(".sidebar-overlay")

  const toggleSidebar = () => {
    if (window.innerWidth <= 1200) {
      // Mobile: Show/hide sidebar with overlay
      sidebar?.classList.toggle("open")
      overlay?.classList.toggle("show")
    } else {
      // Desktop: Collapse/expand sidebar and adjust main content
      sidebar?.classList.toggle("collapsed")
      mainContent?.classList.toggle("expanded")
    }
  }

  // Event listeners
  sidebarToggle?.addEventListener("click", toggleSidebar)
  overlay?.addEventListener("click", toggleSidebar)

  // Reset sidebar state on window resize
  window.addEventListener("resize", () => {
    if (window.innerWidth > 1200) {
      overlay?.classList.remove("show")
      sidebar?.classList.remove("open")
    }
  })
}
