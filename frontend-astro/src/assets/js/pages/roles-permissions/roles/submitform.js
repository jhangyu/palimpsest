document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("roleForm")
  const submitBtn = form.querySelector('button[type="submit"]')
  const spinner =
    '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>'

  // Function to show error feedback
  function showError(input, message) {
    const formGroup = input.closest(".mb-3")
    formGroup.classList.add("has-validation")
    input.classList.add("is-invalid")

    // Remove existing error message if any
    const existingFeedback = formGroup.querySelector(".invalid-feedback")
    if (existingFeedback) {
      existingFeedback.remove()
    }

    // Add new error message
    const feedback = document.createElement("div")
    feedback.className = "invalid-feedback"
    feedback.textContent = message
    input.after(feedback)
  }

  // Function to clear error feedback
  function clearError(input) {
    const formGroup = input.closest(".mb-3")
    formGroup.classList.remove("has-validation")
    input.classList.remove("is-invalid")
    const feedback = formGroup.querySelector(".invalid-feedback")
    if (feedback) {
      feedback.remove()
    }
  }

  // Function to generate slug from title
  function generateSlug(title) {
    return title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
  }

  // Function to validate form
  function validateForm() {
    let isValid = true
    const roleName = form.querySelector("#roleName")
    const roleSlug = form.querySelector("#roleSlug");

    // Clear previous errors
    [roleName, roleSlug].forEach((input) => clearError(input))

    // Validate Role Name
    if (!roleName.value.trim()) {
      showError(roleName, "Role name is required")
      isValid = false
    }

    // Validate Role Slug
    if (!roleSlug.value.trim()) {
      showError(roleSlug, "Role slug is required")
      isValid = false
    } else if (!/^[a-z0-9_]+$/.test(roleSlug.value)) {
      showError(
        roleSlug,
        "Role slug should contain only lowercase letters, numbers and underscores"
      )
      isValid = false
    }

    return isValid
  }

  // Auto-generate slug from name
  form.querySelector("#roleName").addEventListener("input", function () {
    form.querySelector("#roleSlug").value = generateSlug(this.value)
  })

  // Form submission handler
  form.addEventListener("submit", async function (e) {
    e.preventDefault()

    if (!validateForm()) {
      return
    }

    // Show loading state
    submitBtn.disabled = true
    submitBtn.innerHTML = spinner + "Creating..."

    try {
      // Simulate API call (replace with your actual API endpoint)
      await new Promise((resolve) => setTimeout(resolve, 2000))

      // On success
      window.location.href = "/pages/roles-permissions/roles/list"
    } catch (error) {
      // On error
      console.error("Error:", error)
      submitBtn.disabled = false
      submitBtn.innerHTML = "Create Role"

      // Show error alert
      const alert = document.createElement("div")
      alert.className = "alert alert-danger mt-3"
      alert.textContent = "An error occurred while creating the role. Please try again."
      form.insertBefore(alert, form.firstChild)

      // Remove alert after 5 seconds
      setTimeout(() => alert.remove(), 5000)
    }
  })

  // Real-time validation on input
  form.querySelectorAll("input").forEach((input) => {
    input.addEventListener("input", function () {
      clearError(this)
    })
  })
})
