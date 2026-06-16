import { getPathPrefix } from "../../path-utils.js"

document.addEventListener("DOMContentLoaded", function () {
  // Form validation and submission
  const form = document.getElementById("userForm")
  if (!form) return

  const submitBtn = form.querySelector('button[type="submit"]')
  if (!submitBtn) return

  const spinner =
    '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>'

  // Avatar preview functionality
  const avatarInput = document.getElementById("avatarInput")
  const avatarPreview = document.querySelector(".avatar-preview img")
  const defaultAvatar = avatarPreview ? avatarPreview.src : "" // Store default avatar URL

  function handleAvatarChange(event) {
    if (!avatarPreview) return
    const file = event.target.files[0]

    if (file) {
      // Validate file type
      const allowedTypes = ["image/png", "image/jpg", "image/jpeg", "image/webp"]
      if (!allowedTypes.includes(file.type)) {
        alert("Please select a valid image file (PNG, JPG, JPEG, or WebP)")
        avatarInput.value = "" // Clear the input
        avatarPreview.src = defaultAvatar // Reset to default avatar
        return
      }

      // Validate file size (max 5MB)
      const maxSize = 5 * 1024 * 1024 // 5MB in bytes
      if (file.size > maxSize) {
        alert("Image size should be less than 5MB")
        avatarInput.value = "" // Clear the input
        avatarPreview.src = defaultAvatar // Reset to default avatar
        return
      }

      // Create FileReader to display preview
      /* global FileReader */
      const reader = new FileReader()
      reader.onload = function (e) {
        avatarPreview.src = e.target.result
      }
      reader.readAsDataURL(file)
    } else {
      // No file selected or file selection cancelled
      avatarPreview.src = defaultAvatar
    }
  }

  // Add event listeners for avatar changes
  if (avatarInput) {
    avatarInput.addEventListener("change", handleAvatarChange)
  }

  // Form submission handler
  form.addEventListener("submit", async function (e) {
    e.preventDefault()

    // Clear previous error messages
    document.querySelectorAll(".is-invalid").forEach((el) => el.classList.remove("is-invalid"))
    document.querySelectorAll(".invalid-feedback").forEach((el) => el.remove())

    // Validate required fields
    let isValid = true
    const requiredFields = {
      fullName: "Full Name is required",
      email: "Email is required",
      username: "Username is required"
    }

    // Add password validation only if it's the add form (presence of generatePassword button)
    if (document.getElementById("generatePassword")) {
      requiredFields.password = "Password is required"
    }

    // Check required fields
    for (const [fieldId, errorMessage] of Object.entries(requiredFields)) {
      const field = document.getElementById(fieldId)
      if (!field.value.trim()) {
        isValid = false
        field.classList.add("is-invalid")
        const feedback = document.createElement("div")
        feedback.className = "invalid-feedback"
        feedback.textContent = errorMessage
        field.parentNode.appendChild(feedback)
      }
    }

    // Email validation
    const emailField = document.getElementById("email")
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (emailField.value.trim() && !emailRegex.test(emailField.value.trim())) {
      isValid = false
      emailField.classList.add("is-invalid")
      const feedback = document.createElement("div")
      feedback.className = "invalid-feedback"
      feedback.textContent = "Please enter a valid email address"
      emailField.parentNode.appendChild(feedback)
    }

    // Password validation
    const passwordField = document.getElementById("password")
    if (passwordField && passwordField.value.trim()) {
      const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/
      if (!passwordRegex.test(passwordField.value)) {
        isValid = false
        passwordField.classList.add("is-invalid")
        const feedback = document.createElement("div")
        feedback.className = "invalid-feedback"
        feedback.textContent =
          "Password must be at least 8 characters long and include uppercase, lowercase, number and special character"
        passwordField.parentNode.appendChild(feedback)
      }
    }

    // Role validation
    const roleSelected = document.querySelector('input[name="role"]:checked')
    if (!roleSelected) {
      isValid = false
      const roleContainer = document.querySelector(".row.g-3")
      roleContainer.classList.add("is-invalid")
      const feedback = document.createElement("div")
      feedback.className = "invalid-feedback d-block"
      feedback.textContent = "Please select a role"
      roleContainer.appendChild(feedback)
    }

    if (!isValid) {
      // Scroll to the first error
      const firstError = document.querySelector(".is-invalid")
      if (firstError) {
        firstError.scrollIntoView({ behavior: "smooth", block: "center" })
      }
      return
    }

    // Show loading state
    submitBtn.disabled = true
    submitBtn.innerHTML =
      spinner + (document.getElementById("generatePassword") ? "Creating..." : "Saving...")

    try {
      // On success
      window.location.href = getPathPrefix("/users/list")
    } catch (error) {
      // On error
      console.error("Error:", error)
      submitBtn.disabled = false
      submitBtn.innerHTML = document.getElementById("generatePassword")
        ? "Create User"
        : "Save Changes"

      // Show error alert
      const alert = document.createElement("div")
      alert.className = "alert alert-danger mt-3"
      alert.textContent = `An error occurred while ${document.getElementById("generatePassword") ? "creating" : "updating"} the user. Please try again.`
      form.insertBefore(alert, form.firstChild)

      // Remove alert after 5 seconds
      setTimeout(() => alert.remove(), 5000)
    }
  })
})
