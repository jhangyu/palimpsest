import { getPathPrefix } from '../../../path-utils.js'

// Class definition
var GroupsDatatable = (function () {
  // Shared variables
  var dt

  // Private functions
  var initDatatable = function () {
    dt = $('#table_groups').DataTable({
      searchDelay: 500,
      processing: true,
      order: [1, 'asc'],
      lengthMenu: [5, 10, 50, 100],
      iDisplayLength: 5,
      select: {
        style: 'multi',
        selector: 'td:first-child input[type="checkbox"]',
        className: 'row-selected'
      },
      columnDefs: [
        {
          targets: 0,
          orderable: false,
          searchable: false,
          className: 'select-checkbox',
          render: function (data) {
            return `<div class="form-check">
                            <input class="form-check-input bulk-select" type="checkbox" value="${data}">
                        </div>`
          }
        },
        {
          targets: 1,
          render: function (data) {
            return `<div class="d-flex align-items-center">
                            <div>
                                <h6 class="mb-0">${data}</h6>
                            </div>
                        </div>`
          }
        },
        {
          targets: 2,
          render: function (data) {
            return `<span class="text-muted">${data}</span>`
          }
        },
        {
          targets: 3,
          render: function (data) {
            const statusClasses = {
              Active: 'success',
              Inactive: 'warning',
              Trashed: 'danger'
            }
            return `<span class="badge bg-${statusClasses[data]}">${data}</span>`
          }
        },
        {
          targets: -1,
          data: null,
          orderable: false,
          className: 'text-end',
          render: function () {
            return (
              `
                  <div class="dropdown text-end">
                      <button class="btn btn-light btn-active-light-primary dropdown-toggle shadow-none action-btn" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                          Actions
                      </button>
                      <ul class="dropdown-menu">
                        <li><a class="dropdown-item d-flex align-items-center gap-2" href="` +
              getPathPrefix('/roles-permissions/groups/edit') +
              `"><i class="ri-pencil-line"></i> Edit</a></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item d-flex align-items-center gap-2 text-danger delete-button" href="#"><i class="ri-delete-bin-line"></i> Delete</a></li>
                      </ul>
                  </div>`
            )
          }
        }
      ]
    })

    // Re-init functions on every table re-draw
    dt.on('draw', function () {
      initToggleToolbar()
      toggleToolbars()
      handleFilterData()
      initRowDelete()
    })
  }

  // Search Datatable
  var handleSearchDatatable = function () {
    const filterSearch = document.querySelector('[data-table-filter="search"]')
    filterSearch.addEventListener('keyup', function () {
      if (this.value != '') {
        $('.search-clear').show()
      } else {
        $('.search-clear').hide()
      }
      dt.search(this.value).draw()
    })

    const filterSearchClear = document.querySelector('.search-clear')
    filterSearchClear.addEventListener('click', function () {
      $(this).hide()
      $(this).closest('div').find('[data-table-filter="search"]').val('')
      dt.search('').draw()
    })
  }

  // Filter Datatable
  var handleFilterDatatable = () => {
    const filterButton = document.querySelector('[data-table-filter-btn="filter"]')

    // Filter datatable on submit
    filterButton.addEventListener('click', function () {
      $('.dataTables_wrapper').addClass('processing')
      $('.dataTables_processing').css('display', 'block')
      $.fn.dataTable.ext.search = []
      dt.draw()
      handleFilterDataRows()

      // Trigger the dismiss click on the close button
      document.querySelector('#filterDrawer [data-bs-dismiss="offcanvas"]').click()
    })
  }

  // Handle filter data
  var handleFilterDataRows = () => {
    // Get all filter values
    let statusFilters = []
    // get active status from navigation data-type="navbar"
    $('[data-type="navbar"]').each(function () {
      if ($(this).hasClass('active')) {
        if ($(this).attr('data-value') != 'all') {
          statusFilters.push($(this).attr('data-value'))
        }
      }
    })

    // Get checked status from filter drawer
    $('input[name="status"]:checked').each(function () {
      statusFilters.push($(this).val())
    })

    // Add custom filtering
    $.fn.dataTable.ext.search.push(function (_settings, data) {
      let rowStatus = data[3].toLowerCase() // Status column

      // Status filter
      let statusMatch =
        statusFilters.length === 0 || statusFilters.some((status) => rowStatus.includes(status))

      return statusMatch
    })

    // Simulate loading delay
    setTimeout(function () {
      dt.draw()
      $('.dataTables_wrapper').removeClass('processing')
      $('.dataTables_processing').css('display', 'none')
    }, 500)
  }

  // Reset Filter
  var handleResetForm = () => {
    // Select reset button
    const resetButton = document.querySelector('[data-table-filter-btn="reset"]')

    // Reset datatable
    resetButton.addEventListener('click', function () {
      $('.dataTables_wrapper').addClass('processing')
      $('.dataTables_processing').css('display', 'block')

      if ($('.form-check-input:checked').length > 0) {
        $('.form-check-input').prop('checked', false)
      }
      if ($('#filterDrawer .form-select').length > 0) {
        $('#filterDrawer .form-select').val('')
      }

      $('[data-table-filter="search"]').val('')
      $('.search-clear').hide()

      $.fn.dataTable.ext.search = [] // Remove all custom filters

      // Simulate loading delay
      setTimeout(function () {
        dt.draw()
        $('.dataTables_wrapper').removeClass('processing')
        $('.dataTables_processing').css('display', 'none')
      }, 500)

      // Trigger the dismiss click on the close button
      document.querySelector('#filterDrawer [data-bs-dismiss="offcanvas"]').click()
    })
  }

  // Handle filter data display
  var handleFilterData = () => {
    const filterDataView = document.querySelector('[data-filters]')
    const filterData = document.querySelector('[data-filters-data]')
    var search_html = ''

    const filterSearch = document.querySelector('[data-table-filter="search"]')
    var searchval = filterSearch.value
    if (searchval != '') {
      search_html +=
        '<span class="badge text-bg-primary d-flex justify-content-between fs-7 me-2 fw-bold align-items-center">Search: ' +
        searchval +
        ' <span class="ri-close-line cursor-pointer fs-7 fw-bold ms-2 text-inverse clear-filter" data-type="input" data-filter="search"></span></span>'
    }

    // Add status filters
    $('input[name="status"]:checked').each(function () {
      var title = $(this).attr('data-title')
      var val = $(this).val()
      search_html +=
        '<span class="badge text-bg-primary d-flex justify-content-between fs-7 me-2 fw-bold align-items-center">Status: ' +
        title +
        ' <span class="ri-close-line cursor-pointer fs-7 fw-bold ms-2 text-inverse clear-filter" data-val="' +
        val +
        '" data-type="checkbox" data-filter="status"></span></span>'
    })

    if (search_html != '') {
      // Create clear all button element
      const clearAllButton = document.createElement('span')
      clearAllButton.className =
        'badge text-bg-danger fs-7 me-2 d-flex align-items-center fw-semibold cursor-pointer clear-filter'
      clearAllButton.setAttribute('data-filter', 'all')
      clearAllButton.textContent = 'Clear All'

      // Clear existing content
      filterData.textContent = ''

      // Add the search HTML content safely
      const tempDiv = document.createElement('div')
      tempDiv.innerHTML = search_html
      while (tempDiv.firstChild) {
        filterData.appendChild(tempDiv.firstChild)
      }

      // Add the clear all button
      filterData.appendChild(clearAllButton)

      filterDataView.classList.remove('d-none')
      filterDataView.classList.add('d-flex')
      clearFilters()
    } else {
      filterDataView.classList.remove('d-flex')
      filterDataView.classList.add('d-none')
    }
  }

  // Clear filters
  var clearFilters = function () {
    if ($('.clear-filter').length > 0) {
      $('.clear-filter').on('click', function () {
        var filter = $(this).attr('data-filter')
        var type = $(this).attr('data-type')

        if (filter == 'all') {
          $('[data-table-filter="search"]').val('')
          $('[data-table-filter]').each(function () {
            var elementType = $(this).attr('data-type')
            if (elementType == 'checkbox') {
              $(this).prop('checked', false)
            }
          })

          $('.search-clear').hide()
        } else {
          if (type == 'checkbox') {
            var val = $(this).attr('data-val')
            var checkboxFilter = $('[data-table-filter="' + filter + '"]:checked')
            checkboxFilter.each(function () {
              if ($(this).val() == val) {
                $(this).prop('checked', false)
              }
            })
          } else {
            var otherFilter = $('[data-table-filter="' + filter + '"]')
            otherFilter.val('')
          }
        }

        $('.dataTables_wrapper').addClass('processing')
        $('.dataTables_processing').css('display', 'block')
        $.fn.dataTable.ext.search = []
        setTimeout(function () {
          handleFilterDataRows()
          dt.draw()
        }, 500)
      })
    }
  }

  // Init toggle toolbar
  var initToggleToolbar = function () {
    // Toggle selected action toolbar
    const container = document.querySelector('#table_groups')
    const checkboxes = container.querySelectorAll('[type="checkbox"]')

    // Select all checkboxes
    const selectAll = document.querySelector('[data-table-select="select_all"]')
    selectAll.addEventListener('change', function (e) {
      const checkboxes = container.querySelectorAll('[type="checkbox"]')
      checkboxes.forEach((c) => {
        c.checked = e.target.checked
      })
      toggleToolbars()
    })

    // Select elements
    const deleteSelected = document.querySelector('[data-table-select="delete_selected"]')

    // Toggle delete selected toolbar
    checkboxes.forEach((c) => {
      // Checkbox on click event
      c.addEventListener('change', function () {
        setTimeout(function () {
          toggleToolbars()
        }, 50)
      })
    })

    // Deleted selected rows
    deleteSelected.addEventListener('click', function () {
      const selectedIds = []
      let modalTitleText = 'Delete Groups'
      let modalMsgText = 'Are you sure you want to delete selected groups?'
      let modalConfirmTextVal = 'Yes, delete it!'
      let modalLoaderTextVal = 'Deleting...'

      var selectedcheckboxes = container.querySelectorAll('[type="checkbox"]:checked')
      selectedcheckboxes.forEach((sc) => {
        selectedIds.push(sc.value)
      })

      $('#confirmationModal').on('show.bs.modal', function () {
        var modal = $('#confirmationModal')
        modal.find('.modal-body #confirm-yes').text(modalConfirmTextVal)
        modal.find('.modal-body #modal-help-title').text(modalTitleText)
        modal.find('.modal-body #modal-help-text').text(modalMsgText)
        modal.find('.modal-help-content').find('.modal-help-icon').show()
      })

      $('#confirmationModal').modal('show')

      $('#confirmationModal button#confirm-yes')
        .off()
        .on('click', function () {
          var modal = $('#confirmationModal')
          $(this).text(modalLoaderTextVal)

          setTimeout(function () {
            modal.find('.modal-body #modal-buttons').removeClass('d-flex')
            modal.find('.modal-body #modal-buttons').addClass('d-none')
            modal.find('.modal-body #modal-help-title').addClass('text-success').text('Success')
            modal
              .find('.modal-body #modal-help-text')
              .text('Groups have been deleted successfully.')
            modal
              .find('.modal-help-content')
              .find('.modal-help-icon')
              .html('<span class="ri-checkbox-circle-line text-success"></span>')
            modal.find('.modal-help-content').find('.modal-help-icon').show()
          }, 1000)

          setTimeout(function () {
            $('#confirmationModal').modal('hide')
            modal.find('.modal-body #modal-buttons').removeClass('d-none')
            modal.find('.modal-body #modal-buttons').addClass('d-flex')
          }, 3000)
        })

      $('#confirmationModal button#confirm-no')
        .off()
        .on('click', function () {
          $('#confirmationModal').modal('hide')
        })
    })
  }

  // Toggle toolbars
  var toggleToolbars = function () {
    // Define variables
    const container = document.querySelector('#table_groups')
    const toolbarBase = document.querySelector('[data-table-toolbar="filter"]')
    const toolbarSelected = document.querySelector('[data-table-toolbar="bulk_selected"]')
    const selectedCount = document.querySelector('[data-table-select="selected_count"]')

    // Select refreshed checkbox DOM elements
    const allCheckboxes = container.querySelectorAll('tbody [type="checkbox"]')

    // Detect checkboxes state & count
    let checkedState = false
    let count = 0

    // Count checked boxes
    allCheckboxes.forEach((c) => {
      if (c.checked) {
        checkedState = true
        count++
      }
    })

    const selectAll = document.querySelector('[data-table-select="select_all"]')
    if (allCheckboxes.length == count) {
      selectAll.checked = true
    } else {
      selectAll.checked = false
    }

    // Toggle toolbars
    if (checkedState) {
      selectedCount.innerHTML = count
      toolbarBase.classList.add('d-none')
      toolbarSelected.classList.remove('d-none')
    } else {
      toolbarBase.classList.remove('d-none')
      toolbarSelected.classList.add('d-none')
    }
  }

  // Init single delete button
  var initRowDelete = function () {
    if ($('.delete-button').length > 0) {
      $('.delete-button').on('click', function (e) {
        e.preventDefault()
        const $title = 'Delete Group'
        const $msg = 'Are you sure you want to delete this group?'
        const $confirmButtonText = 'Yes, delete it!'
        const $loaderButtonText = 'Deleting...'

        $('#confirmationModal').on('show.bs.modal', function () {
          var modal = $('#confirmationModal')
          modal.find('.modal-body #confirm-yes').text($confirmButtonText)
          modal.find('.modal-body #modal-help-title').text($title)
          modal.find('.modal-body #modal-help-text').text($msg)
          modal.find('.modal-help-content').find('.modal-help-icon').show()
        })

        $('#confirmationModal').modal('show')

        $('#confirmationModal button#confirm-yes')
          .off()
          .on('click', function () {
            var modal = $('#confirmationModal')
            $(this).text($loaderButtonText)

            setTimeout(function () {
              modal.find('.modal-body #modal-buttons').removeClass('d-flex')
              modal.find('.modal-body #modal-buttons').addClass('d-none')
              modal.find('.modal-body #modal-help-title').addClass('text-success').text('Success')
              modal
                .find('.modal-body #modal-help-text')
                .text('Group has been deleted successfully.')
              modal
                .find('.modal-help-content')
                .find('.modal-help-icon')
                .html('<span class="ri-checkbox-circle-line text-success"></span>')
              modal.find('.modal-help-content').find('.modal-help-icon').show()
            }, 1000)

            setTimeout(function () {
              $('#confirmationModal').modal('hide')
              modal.find('.modal-body #modal-buttons').removeClass('d-none')
              modal.find('.modal-body #modal-buttons').addClass('d-flex')
            }, 3000)
          })

        $('#confirmationModal button#confirm-no')
          .off()
          .on('click', function () {
            $('#confirmationModal').modal('hide')
          })
      })
    }
  }

  // Public methods
  return {
    init: function () {
      initDatatable()
      handleSearchDatatable()
      handleFilterDatatable()
      handleResetForm()
      initToggleToolbar()
    }
  }
})()

// On document ready
document.addEventListener('DOMContentLoaded', () => {
  GroupsDatatable.init()
})
