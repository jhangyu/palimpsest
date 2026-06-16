const paginations = document.querySelectorAll(".pagination-section")
paginations.forEach((paginate) => {
  const table = paginate.closest(".astero-table").querySelector("table")
  const rowsPerPageSelect = paginate.querySelector(".rowsPerPage")
  const prevButton = paginate.querySelector('[aria-label="Previous"]')
  const nextButton = paginate.querySelector('[aria-label="Next"]')
  const pageNumbers = paginate.querySelectorAll(".page-item:not(:first-child):not(:last-child)")

  let currentPage = 1
  let rowsPerPage = parseInt(rowsPerPageSelect.value)

  function updatePagination() {
    const rows = Array.from(table.querySelectorAll("tbody tr"))
    const totalRows = rows.length
    const totalPages = Math.ceil(totalRows / rowsPerPage)

    // Calculate start and end indexes
    const startIndex = (currentPage - 1) * rowsPerPage
    const endIndex = Math.min(startIndex + rowsPerPage, totalRows)

    // Update records count and showing text
    const showingText = paginate.querySelector(".text-secondary")
    if (showingText) {
      const [fromElement, toElement, totalElement] = showingText.querySelectorAll(".fw-medium")
      if (fromElement && toElement && totalElement) {
        fromElement.textContent = startIndex + 1
        toElement.textContent = endIndex
        totalElement.textContent = totalRows
      }
    }

    // Show/hide rows based on current page
    rows.forEach((row, index) => {
      if (index >= startIndex && index < endIndex) {
        row.style.display = ""
      } else {
        row.style.display = "none"
      }
    })

    // Update pagination buttons state
    prevButton.parentElement.classList.toggle("disabled", currentPage === 1)
    nextButton.parentElement.classList.toggle("disabled", currentPage === totalPages)

    // Update page numbers
    if (pageNumbers.length > 0) {
      // Clear all page numbers first
      pageNumbers.forEach((pageItem) => {
        pageItem.style.display = "none"
      })

      // Function to create and show a page number
      const showPageNumber = (pageNum, index, isActive = false) => {
        if (index < pageNumbers.length) {
          const pageItem = pageNumbers[index]
          pageItem.style.display = ""
          pageItem.querySelector(".page-link").textContent = pageNum
          pageItem.classList.toggle("active", isActive)

          // Add click event listener if not already added and if it's a number
          const pageLink = pageItem.querySelector(".page-link")
          if (!pageLink.hasListener && pageNum !== "...") {
            pageLink.hasListener = true
            pageLink.addEventListener("click", () => {
              currentPage = parseInt(pageNum)
              updatePagination()
            })
          }
        }
      }

      let displayedPages = []

      if (totalPages <= 4) {
        // Show all pages if total pages is 4 or less
        displayedPages = Array.from({ length: totalPages }, (_, i) => i + 1)
      } else {
        // Always include first and last page
        if (currentPage <= 3) {
          // Near the start: 1, 2, 3, ..., last
          displayedPages = [1, 2, 3, "...", totalPages]
        } else if (currentPage >= totalPages - 1) {
          // Near the end: 1, ..., secondLast, last
          displayedPages = [1, "...", totalPages - 2, totalPages - 1, totalPages]
        } else {
          // In the middle: 1, ..., current, current + 1, ..., last
          displayedPages = [1, "...", currentPage, currentPage + 1, "...", totalPages]
        }
      }

      // Show the calculated pages
      displayedPages.forEach((pageNum, index) => {
        showPageNumber(pageNum, index, pageNum === currentPage)
      })
    }
  }

  // Event Listeners
  rowsPerPageSelect.addEventListener("change", function () {
    rowsPerPage = parseInt(this.value)
    currentPage = 1
    updatePagination()
  })

  prevButton.addEventListener("click", function () {
    if (currentPage > 1) {
      currentPage--
      updatePagination()
    }
  })

  nextButton.addEventListener("click", function () {
    const totalRows = table.querySelectorAll("tbody tr").length
    const totalPages = Math.ceil(totalRows / rowsPerPage)
    if (currentPage < totalPages) {
      currentPage++
      updatePagination()
    }
  })

  // Add resize listener for responsive pagination
  window.addEventListener("resize", () => {
    updatePagination()
  })

  // Initial pagination
  updatePagination()
})
