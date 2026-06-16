/* global CustomEvent */
// Retrieves user's preferred theme from localStorage, defaulting to light
export const getPreferredTheme = () => {
  return localStorage.getItem("theme") || "light"
}

// Updates theme across the application and persists the choice
export const setTheme = (theme) => {
  document.documentElement.setAttribute("data-bs-theme", theme)
  localStorage.setItem("theme", theme)
  updateThemeIcon(theme)
  document.dispatchEvent(new CustomEvent('theme-changed'))
}

// Updates the theme toggle button icon based on current theme
export const updateThemeIcon = (theme) => {
  const icon = document.querySelector("#theme-toggle i")
  if (icon) {
    icon.className = theme === "dark" ? "ri-moon-line fs-5" : "ri-sun-line fs-5"
  }
}

// Initializes theme system and sets up theme toggle functionality
export const darkMode = () => {
  // Apply user's preferred theme on load
  setTheme(getPreferredTheme())

  // Set up theme toggle button click handler
  const themeToggle = document.getElementById("theme-toggle")
  themeToggle?.addEventListener("click", () => {
    const theme = document.documentElement.getAttribute("data-bs-theme")
    setTheme(theme === "dark" ? "light" : "dark")
  })
}
