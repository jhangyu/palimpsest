document.addEventListener("DOMContentLoaded", function () {
  // Module-level expand/collapse all
  document.querySelectorAll(".toggle-module[data-expanded]").forEach((btn) => {
    btn.addEventListener("click", function (e) {
      e.preventDefault()
      const moduleId = this.dataset.moduleId
      const isExpanded = this.dataset.expanded === "true"
      const moduleSection = document.getElementById("module_" + moduleId)
      const icon = this.querySelector("i")
      const text = this.querySelector("span")

      // Toggle all permission groups in this module
      moduleSection.querySelectorAll(".permission-items").forEach((container) => {
        if (isExpanded) {
          new bootstrap.Collapse(container, { toggle: false }).hide()
        } else {
          new bootstrap.Collapse(container, { toggle: false }).show()
        }
      })

      // Update all group toggle icons in this module
      moduleSection.querySelectorAll(".toggle-permissions i").forEach((icon) => {
        if (isExpanded) {
          icon.classList.remove("ri-subtract-line")
          icon.classList.add("ri-add-line")
        } else {
          icon.classList.remove("ri-add-line")
          icon.classList.add("ri-subtract-line")
        }
      })

      // Update button state
      this.dataset.expanded = (!isExpanded).toString()
      if (isExpanded) {
        icon.classList.remove("ri-subtract-line")
        icon.classList.add("ri-add-line")
        if (text) text.textContent = "Expand All"
      } else {
        icon.classList.remove("ri-add-line")
        icon.classList.add("ri-subtract-line")
        if (text) text.textContent = "Collapse All"
      }
    })
  })

  // Toggle module permissions
  document.querySelectorAll(".toggle-module").forEach((checkbox) => {
    checkbox.addEventListener("change", function () {
      const moduleId = this.dataset.moduleId
      const moduleSection = document.getElementById("module_" + moduleId)
      const groupCheckboxes = moduleSection.querySelectorAll(".toggle-group")
      const permissionCheckboxes = moduleSection.querySelectorAll(".permission-checkbox")

      // Check/uncheck all groups and permissions in this module
      groupCheckboxes.forEach((groupCheckbox) => {
        groupCheckbox.checked = this.checked
        groupCheckbox.indeterminate = false
      })

      // Check/uncheck all permissions
      permissionCheckboxes.forEach((permissionCheckbox) => {
        permissionCheckbox.checked = this.checked
      })

      // Update module checkbox state
      this.indeterminate = false
    })
  })

  // Toggle group permissions
  document.querySelectorAll(".toggle-group").forEach((checkbox) => {
    checkbox.addEventListener("change", function () {
      const groupId = this.dataset.groupId
      const permissionsContainer = document.getElementById("permissions_" + groupId)
      const permissionCheckboxes = permissionsContainer.querySelectorAll(".permission-checkbox")

      // Check/uncheck all permissions in this group
      permissionCheckboxes.forEach((permissionCheckbox) => {
        permissionCheckbox.checked = this.checked
      })

      // Update module checkbox state
      updateModuleCheckbox(this)
    })
  })

  // Toggle permission items visibility
  document.querySelectorAll(".toggle-permissions").forEach((button) => {
    button.addEventListener("click", function (e) {
      e.preventDefault()
      const groupId = this.dataset.groupId
      const permissionsContainer = document.getElementById("permissions_" + groupId)

      // Toggle collapse
      new bootstrap.Collapse(permissionsContainer, {
        toggle: true
      })

      // Toggle icon
      const icon = this.querySelector("i")
      if (icon.classList.contains("ri-add-line")) {
        icon.classList.remove("ri-add-line")
        icon.classList.add("ri-subtract-line")
      } else {
        icon.classList.remove("ri-subtract-line")
        icon.classList.add("ri-add-line")
      }
    })
  })

  // Individual permission checkbox change
  document.querySelectorAll(".permission-checkbox").forEach((checkbox) => {
    checkbox.addEventListener("change", function () {
      // Find the group this permission belongs to
      const permissionsContainer = this.closest(".permission-items")
      const groupId = permissionsContainer.id.replace("permissions_", "")
      const groupCheckbox = document.querySelector(
        '[data-group-id="' + groupId + '"].toggle-group'
      )

      // Update group checkbox state
      updateGroupCheckbox(groupCheckbox)

      // Update module checkbox state
      updateModuleCheckbox(groupCheckbox)
    })
  })

  // Function to update module checkbox state based on its groups
  function updateModuleCheckbox(groupCheckbox) {
    // Find the module this group belongs to
    const moduleSection = groupCheckbox.closest(".module-section")
    const moduleId = moduleSection.id.replace("module_", "")
    const moduleCheckbox = document.querySelector(
      '[data-module-id="' + moduleId + '"].toggle-module'
    )
    const groupCheckboxes = moduleSection.querySelectorAll(".toggle-group")

    // Count checked and indeterminate groups
    let checkedGroups = 0
    let indeterminateGroups = 0

    groupCheckboxes.forEach((checkbox) => {
      if (checkbox.checked) {
        checkedGroups++
      } else if (checkbox.indeterminate) {
        indeterminateGroups++
      }
    })

    // Update module checkbox state
    if (checkedGroups === groupCheckboxes.length) {
      moduleCheckbox.checked = true
      moduleCheckbox.indeterminate = false
    } else if (checkedGroups > 0 || indeterminateGroups > 0) {
      moduleCheckbox.checked = false
      moduleCheckbox.indeterminate = true
    } else {
      moduleCheckbox.checked = false
      moduleCheckbox.indeterminate = false
    }
  }

  // Function to update group checkbox state based on its permissions
  function updateGroupCheckbox(groupCheckbox) {
    const groupId = groupCheckbox.dataset.groupId
    const permissionsContainer = document.getElementById("permissions_" + groupId)
    const permissionCheckboxes = permissionsContainer.querySelectorAll(".permission-checkbox")
    const checkedPermissions = permissionsContainer.querySelectorAll(
      ".permission-checkbox:checked"
    )

    // If all permissions are checked, check the group checkbox
    // If some permissions are checked, make group checkbox indeterminate
    // If no permissions are checked, uncheck the group checkbox
    if (checkedPermissions.length === permissionCheckboxes.length) {
      groupCheckbox.checked = true
      groupCheckbox.indeterminate = false
    } else if (checkedPermissions.length > 0) {
      groupCheckbox.checked = false
      groupCheckbox.indeterminate = true
    } else {
      groupCheckbox.checked = false
      groupCheckbox.indeterminate = false
    }

    // Update the parent module checkbox state
    updateModuleCheckbox(groupCheckbox)
  }

  // Initialize all group checkboxes
  document.querySelectorAll(".toggle-group").forEach(updateGroupCheckbox)

  // Initialize all module checkboxes
  document.querySelectorAll(".toggle-module").forEach((moduleCheckbox) => {
    const moduleId = moduleCheckbox.dataset.moduleId
    const moduleSection = document.getElementById("module_" + moduleId)
    const groupCheckboxes = moduleSection.querySelectorAll(".toggle-group")

    if (groupCheckboxes.length > 0) {
      // Update module state based on group states
      const firstGroupCheckbox = groupCheckboxes[0]
      updateModuleCheckbox(firstGroupCheckbox)
    }
  })
})
