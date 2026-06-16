import { getAssetPrefix, getPathPrefix } from '../../../js/path-utils.js'

let data_url = getAssetPrefix('/assets/data/users.json')
let assetpath = getAssetPrefix('/assets/')

let pageindex = 0 // Default to first page if not specified

// Class definition
var UsersDatatable = (function () {
  // Shared variables
  var dt

  // Private functions
  var initDatatable = function () {
    dt = $('#table_users').DataTable({
      searchDelay: 500,
      processing: true,
      data: [],
      order: [1, 'asc'],
      lengthMenu: [10, 25, 50, 100],
      iDisplayLength: 10,
      select: {
        style: 'multi',
        selector: 'td:first-child input[type="checkbox"]',
        className: 'row-selected'
      },
      columns: [
        {
          data: null,
          sortable: false,
          searchable: false,
          className: 'select-checkbox',
          render: function (data, type, row) {
            return `<div class="form-check">
                                    <input class="form-check-input bulk-select" type="checkbox" value="${row.id}">
                                </div>`
          }
        },
        {
          data: 'name',
          render: function (data, _type, row) {
            return `<div class="d-flex align-items-center">
                            <div class="avatar avatar-sm me-2">
                                <img src="${assetpath}${row.avatar}" class="rounded-circle" width="40" height="40" style="object-fit: cover;" alt="User">
                            </div>
                            <div>
                                <h6 class="mb-0">${row.name}</h6>
                                <small class="text-muted">${row.email}</small>
                            </div>
                        </div>`
          }
        },
        {
          data: 'role',
          render: function (data) {
            const roleClasses = {
              Admin: 'danger',
              Manager: 'primary',
              Editor: 'info',
              User: 'success'
            }
            return `<span class="badge bg-${roleClasses[data]}-subtle text-${roleClasses[data]}">${data}</span>`
          }
        },
        {
          data: 'last_login',
          render: function (data) {
            return `<span class="text-muted">${data}</span>`
          }
        },
        {
          data: 'status',
          render: function (data) {
            const statusClasses = {
              Active: 'success',
              Inactive: 'warning',
              Blocked: 'danger'
            }
            return `<span class="badge bg-${statusClasses[data]}">${data}</span>`
          }
        },
        {
          data: 'created_date',
          render: function (data) {
            return `<span class="text-muted">${data}</span>`
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
              getPathPrefix('/users/profile') +
              `"><i class="ri-eye-line"></i> View</a></li>

                                    <li><a class="dropdown-item d-flex align-items-center gap-2" href="` +
              getPathPrefix('/users/edit') +
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

    $.getJSON(data_url, function (json) {
      dt.rows.add(json.data).draw()
    })

    dt.on('init', function () {
      if (!isNaN(pageindex)) {
        const pageInfo = dt.page.info()
        var totalpages = pageInfo.pages
        if (pageindex <= totalpages) {
          dt.page(pageindex).draw(false)
        }
      }
    })

    // Re-init functions on every table re-draw -- more info: https://datatables.net/reference/event/draw
    dt.on('draw', function () {
      initToggleToolbar()
      toggleToolbars()
      triggerFilters()
      handleFilterData()
      initRowDelete()
    })
  }

  // Search Datatable --- official docs reference: https://datatables.net/reference/api/search()
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
      // Trigger the dismiss click on the close button
      document.querySelector('#filterDrawer [data-bs-dismiss="offcanvas"]').click()
      $.fn.dataTable.ext.search = []
      dt.draw()
      handleFilterDataRows()
    })
  }

  // handle filder data
  var handleFilterDataRows = () => {
    // Get all filter values
    let statusFilters = []
    // get active status from navimagion data-type="navbar"
    $('[data-type="navbar"]').each(function () {
      if ($(this).hasClass('active')) {
        if ($(this).attr('data-value') != 'all') {
          statusFilters.push($(this).attr('data-value'))
        }
      }
    })

    let roleFilter = $('#role').val()

    // Add custom filtering
    $.fn.dataTable.ext.search.push(function (_settings, data) {
      let rowStatus = data[4].toLowerCase() // Status column
      let rowRole = data[2].toLowerCase() // Role column

      // Status filter
      let statusMatch = statusFilters.length === 0 || statusFilters.includes(rowStatus)

      // Role filter
      let roleMatch = !roleFilter || rowRole === roleFilter.toLowerCase()

      return statusMatch && roleMatch
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
      // Reset datatable --- official docs reference: https://datatables.net/reference/api/search()
      $('.dataTables_wrapper').addClass('processing')
      $('.dataTables_processing').css('display', 'block')
      // Trigger the dismiss click on the close button
      document.querySelector('#filterDrawer [data-bs-dismiss="offcanvas"]').click()

      if ($('.form-check-input:checked').length > 0) {
        $('.form-check-input').prop('checked', false)
      }
      if ($('#filterDrawer .form-select').length > 0) {
        $('#filterDrawer .form-select').val('')
      }

      $('[data-table-filter="search"]').val('')
      $('.search-clear').hide()

      // dt.draw();
      $.fn.dataTable.ext.search = [] // Remove all custom filters

      // Simulate loading delay
      setTimeout(function () {
        dt.draw()
        $('.dataTables_wrapper').removeClass('processing')
        $('.dataTables_processing').css('display', 'none')
      }, 500)
    })
  }

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
    var filteroptions = document.querySelectorAll('[data-table-filter]')
    filteroptions.forEach((r) => {
      var fname = r.getAttribute('name')
      var fid = r.getAttribute('id')
      var label = r.getAttribute('data-label')
      var type = r.getAttribute('data-type')
      if (fname != '') {
        var fvalue = $('#' + fid).val()
        if (fvalue != undefined && fvalue != '') {
          var search_value = fvalue
          if (type == 'multiselect') {
            $('#' + fid + ' option:selected').each(function () {
              var tmp_value = $(this).attr('data-title')
              var val = $(this).val()

              search_html +=
                '<span class="badge text-bg-primary d-flex justify-content-between fs-7 me-2 fw-bold align-items-center">' +
                label +
                ': ' +
                tmp_value +
                ' <span class="ri-close-line cursor-pointer fs-7 fw-bold ms-2 text-inverse clear-filter" data-val="' +
                val +
                '" data-type="' +
                type +
                '" data-filter="' +
                fname +
                '"></span></span>'
            })
          } else if (type == 'checkbox') {
            if (r.checked) {
              search_value = r.getAttribute('data-title')
              var val = r.value

              search_html +=
                '<span class="badge text-bg-primary d-flex justify-content-between fs-7 me-2 fw-bold align-items-center">' +
                label +
                ': ' +
                search_value +
                ' <span class="ri-close-line cursor-pointer fs-7 fw-bold ms-2 text-inverse clear-filter" data-val="' +
                val +
                '" data-type="' +
                type +
                '" data-filter="' +
                fname +
                '"></span></span>'
            }
          } else {
            if (type == 'select') {
              search_value = r.options[r.selectedIndex].getAttribute('data-title')
            }
            search_html +=
              '<span class="badge text-bg-primary d-flex justify-content-between fs-7 me-2 fw-bold align-items-center">' +
              label +
              ': ' +
              search_value +
              ' <span class="ri-close-line cursor-pointer fs-7 fw-bold ms-2 text-inverse clear-filter" data-type="' +
              type +
              '" data-filter="' +
              fname +
              '"></span></span>'
          }
        }
      }
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

  // Init toggle toolbar
  var initToggleToolbar = function () {
    // Toggle selected action toolbar
    const container = document.querySelector('#table_users')
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
      let modalTitleText = 'Trash Data'
      let modalMsgText = 'Are you sure you want to trash selected data?'
      let modalConfirmTextVal = 'Yes, trash it!'
      let modalLoaderTextVal = 'Trashing...'

      if (deleteSelected.getAttribute('data-title')) {
        modalTitleText = deleteSelected.getAttribute('data-title')
      }

      if (deleteSelected.getAttribute('data-message')) {
        modalMsgText = deleteSelected.getAttribute('data-message')
      }

      if (deleteSelected.getAttribute('data-confirmButtonText')) {
        modalConfirmTextVal = deleteSelected.getAttribute('data-confirmButtonText')
      }

      if (deleteSelected.getAttribute('data-loaderButtonText')) {
        modalLoaderTextVal = deleteSelected.getAttribute('data-loaderButtonText')
      }

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
            modal.find('.modal-body #modal-help-text').text('Data has been trashed successfully.')
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
    const container = document.querySelector('#table_users')
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

  var triggerFilters = function () {
    if ($('.trigger-filter').length > 0) {
      $('.trigger-filter').on('click', function () {
        var filter = $(this).attr('data-filter')
        var value = $(this).attr('data-value')
        var tmpfilter = $('[data-table-filter="' + filter + '"]')
        if (tmpfilter.attr('data-type') == 'multiselect') {
          tmpfilter.find('option[value="' + value + '"]').prop('selected', true)
          var updated_val = tmpfilter.val()
          tmpfilter.val(updated_val)
          tmpfilter.trigger('change')
          dt.draw()
        } else if (tmpfilter.attr('data-type') == 'select') {
          tmpfilter.val(value)
          tmpfilter.trigger('change')
          dt.draw()
        }
      })
    }
  }

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
            } else {
              $(this).val('')
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
        // dt.draw();
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

  // init navbar filter
  var initNavbarFilter = function () {
    if ($('[data-type="navbar"]').length > 0) {
      $('[data-type="navbar"]').on('click', function (e) {
        e.preventDefault()
        $('.dataTables_wrapper').addClass('processing')
        $('.dataTables_processing').css('display', 'block')
        $('[data-type="navbar"]').removeClass('active border-bottom border-2 border-dark')
        $(this).addClass('active border-bottom border-2 border-dark')

        $.fn.dataTable.ext.search = []
        setTimeout(function () {
          dt.draw()
          handleFilterDataRows()
        }, 500)
      })
    }
  }

  // init single delete button
  var initRowDelete = function () {
    if ($('.delete-button').length > 0) {
      $('.delete-button').on('click', function (e) {
        e.preventDefault()
        console.log('delete button clicked')
        const $title = 'Trash Data'
        const $msg = 'Are you sure you want to trash selected data?'
        const $confirmButtonText = 'Yes, trash it!'
        const $loaderButtonText = 'Trashing...'

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
              modal.find('.modal-body #modal-help-text').text('Data has been trashed successfully.')
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

  var noSortingColumn = function () {
    if ($('.no-sort').length > 0) {
      $('.no-sort').on('click', function (e) {
        e.preventDefault()
        e.stopPropagation()
      })
    }
  }
  // Public methods
  return {
    init: function () {
      initDatatable()
      handleSearchDatatable()
      initToggleToolbar()
      handleFilterDatatable()
      handleResetForm()
      triggerFilters()
      handleFilterData()
      clearFilters()
      initNavbarFilter()
      noSortingColumn()
    }
  }
})()

// On document ready
document.addEventListener('DOMContentLoaded', () => {
  UsersDatatable.init()
})
