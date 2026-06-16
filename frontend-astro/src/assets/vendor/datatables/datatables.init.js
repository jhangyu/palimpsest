"use strict"

document.addEventListener("DOMContentLoaded", () => {
  if (typeof $.fn.dataTable === "undefined") {
    console.error("DataTables not loaded! Please ensure jQuery and DataTables are loaded first.")
    return
  }

  var defaults = {
    language: {
      info: "Showing _START_ to _END_ of _TOTAL_ records",
      infoEmpty: "Showing no records",
      infoFiltered: "(filtered from _MAX_ total records)",
      zeroRecords: "No matching records found",
      lengthMenu: "_MENU_",
      processing:
        '<span class="spinner-border w-15px h-15px text-muted align-middle me-2"></span> <span class="text-gray-600">Loading...</span>',
      paginate: {
        first: '<i class="ri-arrow-left-double-line"></i>',
        last: '<i class="ri-arrow-right-double-line"></i>',
        next: '<i class="ri-arrow-right-line"></i>',
        previous: '<i class="ri-arrow-left-line"></i>'
      }
    },
    pagingType: "simple_numbers",
    dom:
      "<'table-responsive'tr>" +
      "<'row'" +
      "<'col-sm-12 col-md-5 d-flex align-items-center justify-content-center justify-content-md-start table-toolbar'li>" +
      "<'col-sm-12 col-md-7 d-flex align-items-center justify-content-center justify-content-md-end'p>" +
      ">",
    renderer: "bootstrap"
  }

  // Extend DataTables defaults
  $.extend(true, $.fn.dataTable.defaults, defaults)

  // Extend DataTables classes
  $.extend($.fn.dataTable.ext.classes, {
    sWrapper: "dataTables_wrapper",
    sFilterInput: "form-control form-control-sm form-control-solid",
    sLengthSelect: "form-select form-select-sm form-select-solid",
    sProcessing: "dataTables_processing",
    sPageButton: "paginate_button page-item",
    search: {
      input: "form-control form-control-solid form-control-sm"
    },
    length: {
      select: "form-select form-select-solid form-select-sm"
    }
  })

  // Bootstrap pagination renderer
  DataTable.ext.renderer.pageButton.bootstrap = function (
    settings,
    host,
    idx,
    buttons,
    page,
    pages
  ) {
    var api = new DataTable.Api(settings)
    var classes = settings.oClasses
    var lang = settings.oLanguage.oPaginate
    var aria = settings.oLanguage.oAria.paginate || {}
    var btnDisplay,
      btnClass,
      counter = 0

    var attach = function (container, buttons) {
      var i, ien, node, button
      var clickHandler = function (e) {
        e.preventDefault()
        if (!$(e.currentTarget).hasClass("disabled") && api.page() != e.data.action) {
          api.page(e.data.action).draw("page")
        }
      }

      for (i = 0, ien = buttons.length; i < ien; i++) {
        button = buttons[i]

        if (Array.isArray(button)) {
          attach(container, button)
        } else {
          btnDisplay = ""
          btnClass = ""

          switch (button) {
          case "ellipsis":
            btnDisplay = "&#x2026;"
            btnClass = "disabled"
            break

          case "first":
            btnDisplay = lang.sFirst
            btnClass = button + (page > 0 ? "" : " disabled")
            break

          case "previous":
            btnDisplay = lang.sPrevious
            btnClass = button + (page > 0 ? "" : " disabled")
            break

          case "next":
            btnDisplay = lang.sNext
            btnClass = button + (page < pages - 1 ? "" : " disabled")
            break

          case "last":
            btnDisplay = lang.sLast
            btnClass = button + (page < pages - 1 ? "" : " disabled")
            break

          default:
            btnDisplay = button + 1
            btnClass = page === button ? "active" : ""
            break
          }

          if (btnDisplay) {
            node = $("<li>", {
              class: classes.sPageButton + " " + btnClass,
              id: idx === 0 && typeof button === "string" ? settings.sTableId + "_" + button : null
            })
              .append(
                $("<button>", {
                  "aria-controls": settings.sTableId,
                  "aria-label": aria[button],
                  "data-idx": counter,
                  tabindex: settings.iTabIndex,
                  class: "page-link"
                }).html(btnDisplay)
              )
              .appendTo(container)

            settings.oApi._fnBindAction(node, { action: button }, clickHandler)

            counter++
          }
        }
      }
    }

    // IE9 throws an 'unknown error' if document.activeElement is used
    // inside an iframe or frame.
    var activeEl

    try {
      // Because this approach is destroying and recreating the paging
      // elements, focus is lost on the select button which is bad for
      // accessibility. So we want to restore focus once the draw has
      // completed
      activeEl = $(host).find(document.activeElement).data("idx")
    } catch {
      // Silently handle focus-related errors in iframes/frames
      // This is expected behavior in IE9 and some other browsers
    }

    attach($(host).empty().html('<ul class="pagination"/>').children("ul"), buttons)

    if (activeEl !== undefined) {
      $(host)
        .find("[data-idx=" + activeEl + "]")
        .trigger("focus")
    }
  }
})
