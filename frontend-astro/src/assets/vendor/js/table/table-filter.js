const asterotables = document.querySelectorAll(".astero-table")
asterotables.forEach((astable) => {
  const table = astable.querySelector("table")
  const selectAllCheckbox = table.querySelector(".select-all-checkbox")
  const checkboxes = table.querySelectorAll("tbody .form-check-input")
  const bulkActions = astable.querySelector(".bulk-actions")
  const filterBtn = astable.querySelector(".filter-btn")
  const selectedCountSpan = astable.querySelector(".selected-count")
  const searchInput = astable.querySelector(".search-input")
  const clearBtn = astable.querySelector(".btn-clear")

  // Function to update selected count and visibility
  function updateSelectedState() {
    const selectedCount = Array.from(checkboxes).filter((cb) => cb.checked).length
    selectedCountSpan.textContent = `${selectedCount} ${selectedCount === 1 ? "item" : "items"} selected`

    if (selectedCount > 0) {
      bulkActions.style.display = "flex"
      filterBtn.style.display = "none"
    } else {
      bulkActions.style.display = "none"
      filterBtn.style.display = "flex"
    }
  }

  // Handle select all checkbox
  selectAllCheckbox.addEventListener("change", function () {
    checkboxes.forEach((checkbox) => {
      checkbox.checked = this.checked
    })
    updateSelectedState()
    selectAllCheckbox.indeterminate = false
  })

  // Handle individual checkboxes
  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", function () {
      const totalCheckboxes = checkboxes.length
      const checkedCount = Array.from(checkboxes).filter((cb) => cb.checked).length

      selectAllCheckbox.checked = checkedCount === totalCheckboxes
      selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < totalCheckboxes

      updateSelectedState()
    })
  })

  // Handle bulk delete
  const bulkDeleteBtn = document.querySelector(".bulk-delete")
  bulkDeleteBtn.addEventListener("click", function () {
    const selectedCount = Array.from(checkboxes).filter((cb) => cb.checked).length
    if (confirm(`Are you sure you want to delete ${selectedCount} selected items?`)) {
      // Here you would typically make an API call to delete the items
      console.log("Deleting selected items...")

      // For demo purposes, we'll just uncheck all boxes
      selectAllCheckbox.checked = false
      checkboxes.forEach((checkbox) => {
        checkbox.checked = false
      })
      updateSelectedState()
    }
  })

  // Function to perform search
  function performSearch(searchTerm) {
    const rows = table.querySelectorAll("tbody tr")
    searchTerm = searchTerm.toLowerCase()

    rows.forEach((row) => {
      const text = row.textContent.toLowerCase()
      row.style.display = text.includes(searchTerm) ? "" : "none"
    })

    // Toggle clear button visibility
    clearBtn.style.display = searchTerm ? "flex" : "none"
  }

  // Handle search functionality
  searchInput.addEventListener("input", function () {
    performSearch(this.value)
  })

  // Handle clear button click
  clearBtn.addEventListener("click", function () {
    searchInput.value = ""
    performSearch("")
    searchInput.focus()
  })
})
