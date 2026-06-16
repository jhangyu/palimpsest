// UI Controls Manager for Component Preview System
window.UIControlsManager = class UIControlsManager {
  static CONFIG = {
    COPY_FEEDBACK_DELAY: 1000,
    THEME_SYNC_DELAY: 100,
    MAX_THEME_RETRIES: 3,
    KEYBOARD_SHORTCUTS: true
  }

  static themeVersion = 0

  static setupUIControls() {
    try {
      // console.log('Setting up UI Controls')

      this.setupEditButtons()
      this.setupResetButtons()
      this.setupCopyButtons()
      this.setupPreviewDevices()
      this.setupThemeToggle()
      this.setupPreviewExpand()
      this.setupCodeToggle()
      this.setupDownloadButtons()
      this.setupKeyboardShortcuts()
      this.setupAccessibility()

      console.log('UI Controls setup completed')
    } catch (error) {
      console.error('Error setting up UI Controls:', error)
    }
  }

  static setupEditButtons() {
    document.querySelectorAll('.edit-button').forEach((button) => {
      button.addEventListener('click', () => {
        const card = button.closest('.card')
        const allEditorContainers = card.querySelectorAll('.codemirror-editor-container')
        if (!allEditorContainers.length) return

        const firstEditor = allEditorContainers[0].editor
        if (!firstEditor) return

        const isReadOnly = firstEditor.getOption('readOnly')

        // Toggle edit mode for all editors
        allEditorContainers.forEach((container) => {
          if (container.editor) {
            container.editor.setOption('readOnly', !isReadOnly)

            // Handle edit mode indicator
            let indicator = container.querySelector('.edit-mode-indicator')

            if (!isReadOnly) {
              // Removing edit mode - remove indicator if exists
              if (indicator) {
                indicator.remove()
              }
            } else {
              // Enabling edit mode - add indicator if doesn't exist
              if (!indicator) {
                indicator = document.createElement('div')
                indicator.className =
                  'edit-mode-indicator position-absolute top-0 end-0 m-2 px-2 py-1 bg-primary text-white rounded-pill fs-sm'
                indicator.innerHTML = '<i class="ri-edit-line me-1"></i>Edit Mode'
                indicator.style.zIndex = '10'
                indicator.style.fontSize = '0.75rem'
                indicator.style.opacity = '0.8'
                container.style.position = 'relative'
                container.appendChild(indicator)
              }
            }
          }
        })

        button.classList.toggle('active', !isReadOnly)
        const icon = button.querySelector('i')
        if (icon) {
          if (isReadOnly) {
            icon.classList.remove('ri-edit-line')
            icon.classList.add('ri-save-line')
            button.setAttribute('title', 'Save changes')
            button.setAttribute('aria-label', 'Save changes')
          } else {
            icon.classList.remove('ri-save-line')
            icon.classList.add('ri-edit-line')
            button.setAttribute('title', 'Edit code')
            button.setAttribute('aria-label', 'Edit code')
          }
        }

        const previewBox = card.closest('.preview-box') || card.closest('.preview-modal')
        if (previewBox) {
          // Get the current bgColor value before updating
          const bgColor = previewBox.getAttribute('data-bg-color') === 'true'

          // Update iframe with preserved bgColor
          setTimeout(() => {
            window.PreviewManager.updateIframeContent(previewBox)

            // Force the background color to be applied again
            const iframe = previewBox.querySelector('.preview-iframe')
            if (iframe && iframe.contentWindow) {
              try {
                // Always send the bgColor explicitly to ensure it's preserved
                iframe.contentWindow.postMessage({ type: 'updateContent', bgColor: bgColor }, '*')

                // Force another update after a short delay to ensure the background color sticks
                setTimeout(() => {
                  if (iframe.contentWindow) {
                    iframe.contentWindow.postMessage(
                      { type: 'updateContent', bgColor: bgColor },
                      '*'
                    )
                  }
                }, 500)
              } catch (e) {
                console.error('Error updating background color:', e)
              }
            }
          }, 100)
        }

        // Show feedback based on the current state
        const feedbackMessage = isReadOnly ? 'Edit mode enabled!' : 'Changes saved!'

        // Check if button has tooltip initialized
        let tooltip = bootstrap.Tooltip.getInstance(button)
        if (!tooltip) {
          tooltip = new bootstrap.Tooltip(button, {
            title: button.getAttribute('title'),
            placement: 'top',
            trigger: 'hover focus'
          })
        }

        // Update tooltip content
        const originalTitle = button.getAttribute('title')
        button.setAttribute('title', feedbackMessage)
        tooltip.dispose()
        const newTooltip = new bootstrap.Tooltip(button, {
          title: feedbackMessage,
          placement: 'top',
          trigger: 'manual'
        })
        newTooltip.show()

        // Reset tooltip after 1 second
        setTimeout(() => {
          button.setAttribute('title', originalTitle)
          newTooltip.dispose()
          new bootstrap.Tooltip(button, {
            title: originalTitle,
            placement: 'top'
          })
        }, 1000)
      })
    })
  }

  static setupResetButtons() {
    document.querySelectorAll('.reset-all-button').forEach((button) => {
      button.addEventListener('click', () => {
        const card = button.closest('.card')
        const editors = card.querySelectorAll('.codemirror-editor-container')

        editors.forEach((container) => {
          if (container.editor && container.defaultCode) {
            const editor = container.editor
            editor.setValue(container.defaultCode)
            editor.setOption('readOnly', true)

            // Remove edit mode indicator if exists
            const indicator = container.querySelector('.edit-mode-indicator')
            if (indicator) {
              indicator.remove()
            }

            const editButton = card.querySelector('.edit-button')
            if (editButton) {
              editButton.classList.remove('active')
              const icon = editButton.querySelector('i')
              if (icon) {
                icon.classList.remove('ri-save-line')
                icon.classList.add('ri-edit-line')
                editButton.setAttribute('title', 'Edit code')
                editButton.setAttribute('aria-label', 'Edit code')
              }
            }
          }
        })

        const previewBox = button.closest('.preview-box')
        if (previewBox) {
          window.PreviewManager.updateIframeContent(previewBox)
        }

        // Show reset success feedback
        const originalTitle = button.getAttribute('title') || 'Reset all changes'

        // Check if button has tooltip initialized
        let tooltip = bootstrap.Tooltip.getInstance(button)
        if (!tooltip) {
          tooltip = new bootstrap.Tooltip(button, {
            title: originalTitle,
            placement: 'top',
            trigger: 'hover focus'
          })
        }

        // Update tooltip content
        button.setAttribute('title', 'Reset done!')
        tooltip.dispose()
        const newTooltip = new bootstrap.Tooltip(button, {
          title: 'Reset done!',
          placement: 'top',
          trigger: 'manual'
        })
        newTooltip.show()

        // Reset tooltip after 1 second
        setTimeout(() => {
          button.setAttribute('title', originalTitle)
          newTooltip.dispose()
          new bootstrap.Tooltip(button, {
            title: originalTitle,
            placement: 'top'
          })
        }, 1000)
      })
    })
  }

  static setupCopyButtons() {
    const copyButtons = document.querySelectorAll('.copy-button')

    copyButtons.forEach((button) => {
      button.addEventListener('click', async () => {
        try {
          // Find the closest component preview container
          const componentPreview =
            button.closest('.component-preview') ||
            button.closest('.preview-box') ||
            button.closest('.preview-modal')
          if (!componentPreview) return

          // Find the active tab pane
          const activeTabPane = componentPreview.querySelector('.tab-pane.active')
          if (!activeTabPane) return

          // Get the editor container from the active tab
          const editorContainer = activeTabPane.querySelector('.codemirror-editor-container')
          if (!editorContainer) return

          // Get the editor instance (using the correct property name)
          const editor = editorContainer.editor
          if (!editor) return

          // Get the code from the editor
          const code = editor.getValue()

          // Copy the code to clipboard
          await navigator.clipboard.writeText(code)

          // Show success feedback
          const originalTitle = button.getAttribute('title') || 'Copy to clipboard'

          // Check if button has tooltip initialized
          let tooltip = bootstrap.Tooltip.getInstance(button)
          if (!tooltip) {
            tooltip = new bootstrap.Tooltip(button, {
              title: originalTitle,
              placement: 'top',
              trigger: 'hover focus'
            })
          }

          // Update tooltip content
          button.setAttribute('title', 'Copied!')
          tooltip.dispose()
          const newTooltip = new bootstrap.Tooltip(button, {
            title: 'Copied!',
            placement: 'top',
            trigger: 'manual'
          })
          newTooltip.show()

          // Reset tooltip after 1 second
          setTimeout(() => {
            button.setAttribute('title', originalTitle)
            newTooltip.dispose()
            new bootstrap.Tooltip(button, {
              title: originalTitle,
              placement: 'top'
            })
          }, 1000)
        } catch (error) {
          console.error('Failed to copy code:', error)
        }
      })
    })
  }

  static setupPreviewDevices() {
    document.querySelectorAll('.preview-devices').forEach((devices) => {
      devices.querySelectorAll('.btn').forEach((button) => {
        button.addEventListener('click', () => {
          const width = button.dataset.width
          const previewBox = button.closest('.preview-box') || button.closest('.preview-modal')
          if (!previewBox) return

          this.updatePreviewWidth(previewBox, width)

          // Sync with modal or main preview
          if (previewBox.classList.contains('preview-modal')) {
            this.syncModalToMainPreview(previewBox, width)
          } else {
            this.syncMainPreviewToModal(previewBox, width)
          }
        })
      })
    })
  }

  static updatePreviewWidth(element, width) {
    const devices = element.querySelector('.preview-devices')
    if (devices) {
      devices.querySelectorAll('.btn').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.width === width)
        btn.setAttribute('aria-pressed', btn.dataset.width === width)
      })
    }

    const container = element.querySelector('.preview-container')
    if (container) {
      container.style.maxWidth = '100%'
      container.style.width = width === '100%' ? '100%' : `${width}px`
      container.style.margin = width === '100%' ? '0' : '0 auto'
    }
  }

  static syncModalToMainPreview(modal, width) {
    const modalId = modal.id
    const mainPreview =
      document.querySelector(`.preview-box[data-modal="${modalId}"]`) ||
      document.querySelector('.preview-box')
    if (mainPreview) {
      this.updatePreviewWidth(mainPreview, width)
    }
  }

  static syncMainPreviewToModal(previewBox, width) {
    const modalId = previewBox.querySelector('.preview-expand')?.getAttribute('data-bs-target')
    if (modalId) {
      const modal = document.querySelector(modalId)
      if (modal) {
        this.updatePreviewWidth(modal, width)
      }
    }
  }

  static setupThemeToggle() {
    document.querySelectorAll('.theme-toggle').forEach((button) => {
      // Get initial theme from localStorage, document, or default to light
      const storedTheme = localStorage.getItem('theme')
      const documentTheme = document.documentElement.getAttribute('data-bs-theme')
      const initialTheme = storedTheme || documentTheme || 'light'

      // Set initial theme state
      button.dataset.currentTheme = initialTheme
      const icon = button.querySelector('i')
      if (icon) {
        this.updateThemeIcon(icon, initialTheme)
      }

      // Find associated preview box and iframe
      const previewBox = button.closest('.preview-box') || button.closest('.preview-modal')
      if (!previewBox) return

      // Set theme on card-body or modal-body
      if (previewBox.classList.contains('preview-box')) {
        const cardBody = previewBox.querySelector('.card-body')
        if (cardBody) {
          cardBody.setAttribute('data-bs-theme', initialTheme)
        }
      } else if (previewBox.classList.contains('preview-modal')) {
        const modalBody = previewBox.querySelector('.modal-body')
        if (modalBody) {
          modalBody.setAttribute('data-bs-theme', initialTheme)
        }
      }

      const iframe = previewBox.querySelector('.preview-iframe')
      if (!iframe) return

      // Set up iframe load handler
      iframe.addEventListener('load', () => {
        try {
          iframe.contentWindow.postMessage({ type: 'setTheme', theme: initialTheme }, '*')
        } catch (e) {
          console.error('Error setting initial iframe theme:', e)
        }
      })

      // Set up click handler
      button.addEventListener('click', () => {
        const currentTheme = button.dataset.currentTheme || 'light'
        const newTheme = currentTheme === 'light' ? 'dark' : 'light'

        // Update button state
        button.dataset.currentTheme = newTheme
        if (icon) {
          this.updateThemeIcon(icon, newTheme)
        }

        // Store theme preference for this component only (in component-specific key)
        const componentId = previewBox.id || 'default'
        localStorage.setItem(`iframe-theme-${componentId}`, newTheme)

        // Do NOT update the document theme - only components should be affected
        // document.documentElement.setAttribute('data-bs-theme', newTheme)

        // Update only this specific component's iframe and sync with modal/main preview
        this.updateComponentTheme(previewBox, newTheme)
      })

      // Set up theme acknowledgment listener
      this.setupThemeAcknowledgmentListener(button)
    })
  }

  static updateThemeIcon(icon, theme) {
    if (!icon) return

    if (theme === 'dark') {
      icon.classList.remove('ri-sun-line')
      icon.classList.add('ri-moon-line')
      icon.closest('button')?.setAttribute('title', 'Switch to light theme')
      icon.closest('button')?.setAttribute('aria-label', 'Switch to light theme')
    } else {
      icon.classList.remove('ri-moon-line')
      icon.classList.add('ri-sun-line')
      icon.closest('button')?.setAttribute('title', 'Switch to dark theme')
      icon.closest('button')?.setAttribute('aria-label', 'Switch to dark theme')
    }
  }

  static updateComponentTheme(previewBox, theme) {
    if (!previewBox) return

    const iframe = previewBox.querySelector('.preview-iframe')
    if (!iframe) return

    const themeToggle = previewBox.querySelector('.theme-toggle')
    if (themeToggle) {
      themeToggle.dataset.currentTheme = theme
      this.updateThemeIcon(themeToggle.querySelector('i'), theme)

      // Store theme preference for this component
      if (previewBox.id) {
        localStorage.setItem(`iframe-theme-${previewBox.id}`, theme)
      }
    }

    // Get the background color setting
    const bgColor = previewBox.getAttribute('data-bg-color') === 'true'

    // Update data-bs-theme on card-body or modal-body
    if (previewBox.classList.contains('preview-box')) {
      // For main preview, set data-bs-theme on card-body
      const cardBody = previewBox.querySelector('.card-body')
      if (cardBody) {
        cardBody.setAttribute('data-bs-theme', theme)
      }

      // Find and update the associated modal if it exists
      const modalId = previewBox.querySelector('.preview-expand')?.getAttribute('data-bs-target')
      if (modalId) {
        const modal = document.querySelector(modalId)
        if (modal) {
          // Update modal theme toggle
          const modalThemeToggle = modal.querySelector('.theme-toggle')
          if (modalThemeToggle) {
            modalThemeToggle.dataset.currentTheme = theme
            const modalIcon = modalThemeToggle.querySelector('i')
            if (modalIcon) {
              this.updateThemeIcon(modalIcon, theme)
            }
          }

          // Update modal-body theme
          const modalBody = modal.querySelector('.modal-body')
          if (modalBody) {
            modalBody.setAttribute('data-bs-theme', theme)
          }

          // Update modal iframe theme if it exists
          const modalIframe = modal.querySelector('.preview-iframe')
          if (modalIframe && modalIframe.contentWindow) {
            try {
              modalIframe.contentWindow.postMessage(
                {
                  type: 'setTheme',
                  theme: theme,
                  version: ++this.themeVersion
                },
                '*'
              )

              // Also update background color
              modalIframe.contentWindow.postMessage(
                {
                  type: 'updateContent',
                  bgColor: bgColor
                },
                '*'
              )
            } catch (e) {
              console.error('Error updating modal iframe theme:', e)
            }
          }
        }
      }
    } else if (previewBox.classList.contains('preview-modal')) {
      // For modal preview, set data-bs-theme on modal-body
      const modalBody = previewBox.querySelector('.modal-body')
      if (modalBody) {
        modalBody.setAttribute('data-bs-theme', theme)
      }

      // Find and update the associated main preview
      const modalId = previewBox.id
      const mainPreview = document.querySelector(`.preview-box[data-modal="${modalId}"]`)
      if (mainPreview) {
        // Update main preview theme toggle
        const mainThemeToggle = mainPreview.querySelector('.theme-toggle')
        if (mainThemeToggle) {
          mainThemeToggle.dataset.currentTheme = theme
          const mainIcon = mainThemeToggle.querySelector('i')
          if (mainIcon) {
            this.updateThemeIcon(mainIcon, theme)
          }
        }

        // Update card-body theme
        const cardBody = mainPreview.querySelector('.card-body')
        if (cardBody) {
          cardBody.setAttribute('data-bs-theme', theme)
        }

        // Update main preview iframe theme
        const mainIframe = mainPreview.querySelector('.preview-iframe')
        if (mainIframe && mainIframe.contentWindow) {
          try {
            mainIframe.contentWindow.postMessage(
              {
                type: 'setTheme',
                theme: theme,
                version: ++this.themeVersion
              },
              '*'
            )

            // Also update background color
            mainIframe.contentWindow.postMessage(
              {
                type: 'updateContent',
                bgColor: bgColor
              },
              '*'
            )
          } catch (e) {
            console.error('Error updating main preview iframe theme:', e)
          }
        }
      }
    }

    if (!previewBox.dataset.externalSrc) {
      const htmlEditor = window.CodeMirrorManager?.getEditorFromPreviewBox(previewBox, 'html')
      const cssEditor = window.CodeMirrorManager?.getEditorFromPreviewBox(previewBox, 'css')
      const jsEditor = window.CodeMirrorManager?.getEditorFromPreviewBox(previewBox, 'javascript')

      const htmlContent = htmlEditor ? htmlEditor.getValue() : ''
      const cssContent = cssEditor ? cssEditor.getValue() : ''
      const jsContent = jsEditor ? jsEditor.getValue() : ''

      // Update iframe content with new theme
      if (iframe.contentWindow) {
        try {
          iframe.contentWindow.postMessage(
            {
              type: 'setTheme',
              theme: theme,
              version: ++this.themeVersion
            },
            '*'
          )

          // Also update the background color
          iframe.contentWindow.postMessage(
            {
              type: 'updateContent',
              bgColor: bgColor
            },
            '*'
          )
        } catch (e) {
          console.error('Error updating iframe theme:', e)

          // If direct update fails, recreate the iframe content
          if (typeof window.PreviewManager !== 'undefined') {
            const iframeContent = window.PreviewManager.createIframeContent(
              htmlContent,
              cssContent,
              jsContent,
              theme,
              bgColor
            )
            iframe.srcdoc = iframeContent
          }
        }
      } else {
        // If contentWindow is not available, recreate the iframe content
        if (typeof window.PreviewManager !== 'undefined') {
          const iframeContent = window.PreviewManager.createIframeContent(
            htmlContent,
            cssContent,
            jsContent,
            theme,
            bgColor
          )
          iframe.srcdoc = iframeContent
        }
      }
    } else {
      // iframe.src = previewBox.dataset.externalSrc

      if (iframe.contentWindow) {
        try {
          iframe.contentWindow.postMessage({ type: 'setTheme', theme: theme }, '*')

          // Also send background color
          iframe.contentWindow.postMessage({ type: 'updateContent', bgColor: bgColor }, '*')
        } catch (e) {
          console.error('Error updating iframe theme:', e)
        }
      }
    }
  }

  static updateAllIframeThemes(sourcePreviewBox, theme) {
    // Update all theme toggles in the document
    document.querySelectorAll('.theme-toggle').forEach((toggle) => {
      toggle.dataset.currentTheme = theme
      const icon = toggle.querySelector('i')
      if (icon) {
        this.updateThemeIcon(icon, theme)
      }
    })

    // Update main preview iframe
    const mainIframe = sourcePreviewBox.querySelector('.preview-iframe')
    if (mainIframe) {
      this.updateIframeTheme(mainIframe, theme)
    }

    // Find and update modal iframe if exists
    const modalId = sourcePreviewBox
      .querySelector('.preview-expand')
      ?.getAttribute('data-bs-target')
    if (modalId) {
      const modal = document.querySelector(modalId)
      if (modal?.classList.contains('show')) {
        const modalIframe = modal.querySelector('.preview-iframe')
        if (modalIframe) {
          this.updateIframeTheme(modalIframe, theme)
        }
      }
    }

    // If source is modal, update main preview
    if (sourcePreviewBox.classList.contains('preview-modal')) {
      const modalId = sourcePreviewBox.id
      const mainPreview = document.querySelector(`.preview-box[data-modal="${modalId}"]`)
      if (mainPreview) {
        const mainIframe = mainPreview.querySelector('.preview-iframe')
        if (mainIframe) {
          this.updateIframeTheme(mainIframe, theme)
        }
      }
    }

    // Update all iframes in the document
    document.querySelectorAll('.preview-iframe').forEach((iframe) => {
      if (iframe.contentWindow) {
        try {
          iframe.contentWindow.postMessage(
            {
              type: 'setTheme',
              theme: theme,
              version: ++this.themeVersion
            },
            '*'
          )
        } catch (e) {
          console.error('Error updating iframe theme:', e)
        }
      }
    })

    // Update localStorage for iframe theme only
    localStorage.setItem('iframe-theme', theme)
  }

  static updateIframeTheme(iframe, theme, retries = 3) {
    if (!iframe?.contentWindow) return

    const version = ++this.themeVersion
    const tryUpdateTheme = (remainingRetries) => {
      try {
        iframe.contentWindow.postMessage(
          {
            type: 'setTheme',
            theme,
            version
          },
          '*'
        )
      } catch (e) {
        console.error('Error setting iframe theme:', e)
        if (remainingRetries > 0) {
          setTimeout(() => tryUpdateTheme(remainingRetries - 1), 100)
        }
      }
    }

    tryUpdateTheme(retries)
  }

  static setupThemeAcknowledgmentListener(button) {
    // Remove any existing handler
    if (button._themeHandler) {
      window.removeEventListener('message', button._themeHandler)
    }

    const handler = (event) => {
      if (!event.data || event.data.type !== 'themeAcknowledged') return

      const acknowledgedTheme = event.data.theme
      const acknowledgedVersion = event.data.version || 0
      const currentTheme = button.dataset.currentTheme

      // Only update if there's a real mismatch and version is current
      if (acknowledgedTheme !== currentTheme && acknowledgedVersion === this.themeVersion) {
        const retryCount = parseInt(button.dataset.themeRetryCount || '0')
        if (retryCount < this.CONFIG.MAX_THEME_RETRIES) {
          button.dataset.themeRetryCount = (retryCount + 1).toString()
          const previewBox = button.closest('.preview-box') || button.closest('.preview-modal')
          if (previewBox) {
            this.updateAllIframeThemes(previewBox, currentTheme)
          }
        } else {
          console.warn('Max theme sync retries reached, manual refresh may be needed')
          button.dataset.themeRetryCount = '0' // Reset counter for next attempt
        }
      } else {
        // Reset retry count when themes match or version is old
        button.dataset.themeRetryCount = '0'
      }
    }

    // Store handler reference for cleanup
    button._themeHandler = handler
    window.addEventListener('message', handler)
  }

  static setupCodeToggle() {
    document.querySelectorAll('.preview-box').forEach((previewBox) => {
      const toggleBtn = previewBox.querySelector('.code-toggle-link')
      const codePreviewBox = previewBox.querySelector('.code-preview-box')

      if (toggleBtn && codePreviewBox) {
        toggleBtn.addEventListener('click', () => {
          const isHidden = !codePreviewBox.classList.contains('show')

          codePreviewBox.classList.toggle('show')
          toggleBtn.classList.toggle('active')
          toggleBtn.setAttribute('aria-expanded', isHidden ? 'true' : 'false')

          const btnText = toggleBtn.querySelector('span')
          if (btnText) {
            btnText.textContent = isHidden ? 'Hide Code' : 'Show Code'
          }

          const icon = toggleBtn.querySelector('i')
          if (icon) {
            icon.className = isHidden ? 'ri-code-line px-1' : 'ri-code-s-slash-line px-1'
          }

          if (isHidden) {
            // Refresh all editors with a slight delay to ensure DOM is updated
            setTimeout(() => {
              const editors = codePreviewBox.querySelectorAll('.codemirror-editor-container')
              editors.forEach((container) => {
                if (container.editor) {
                  container.editor.refresh()

                  // Force scrollbar refresh
                  const scrollInfo = container.editor.getScrollInfo()
                  container.editor.scrollTo(scrollInfo.left, scrollInfo.top)
                }
              })
            }, 300)
          }
        })
      }
    })
  }

  static setupPreviewExpand() {
    document.querySelectorAll('.preview-expand').forEach((button) => {
      button.addEventListener('click', () => {
        const previewBox = button.closest('.preview-box')
        if (!previewBox) return

        const modalId = button.getAttribute('data-bs-target')
        const modal = document.querySelector(modalId)
        if (!modal || !modal.classList.contains('preview-modal')) return

        previewBox.dataset.modal = modalId.replace('#', '')

        if (typeof bootstrap === 'undefined') {
          console.error('Bootstrap is not loaded')
          return
        }

        const modalIframe = modal.querySelector('.preview-iframe')
        this.syncModalContent(previewBox, modal)

        const icon = button.querySelector('i')
        if (icon) {
          icon.classList.remove('ri-fullscreen-line')
          icon.classList.add('ri-fullscreen-exit-line')
        }

        this.showModal(modal, previewBox, modalIframe)

        modal.addEventListener(
          'hidden.bs.modal',
          () => {
            const icon = button.querySelector('i')
            if (icon) {
              icon.classList.remove('ri-fullscreen-exit-line')
              icon.classList.add('ri-fullscreen-line')
            }

            const modalDevices = modal.querySelector('.preview-devices .btn.active')
            if (modalDevices) {
              const width = modalDevices.dataset.width
              this.updatePreviewWidth(previewBox, width)
            }
          },
          { once: false }
        )
      })
    })
  }

  static showModal(modal, previewBox, modalIframe) {
    const showModalContent = () => {
      if (!previewBox || !modalIframe) return

      // Check if using external source
      const externalSrc = previewBox.dataset.externalSrc
      if (!externalSrc) {
        // For non-external sources, proceed with full content sync
        const htmlEditor = window.CodeMirrorManager?.getEditorFromPreviewBox(previewBox, 'html')
        const cssEditor = window.CodeMirrorManager?.getEditorFromPreviewBox(previewBox, 'css')
        const jsEditor = window.CodeMirrorManager?.getEditorFromPreviewBox(previewBox, 'javascript')

        const htmlContent = htmlEditor ? htmlEditor.getValue() : ''
        const cssContent = cssEditor ? cssEditor.getValue() : ''
        const jsContent = jsEditor ? jsEditor.getValue() : ''

        // Get component-specific theme
        const themeToggle = previewBox.querySelector('.theme-toggle')
        const theme = themeToggle?.dataset.currentTheme || 'light'

        // Get bgColor from preview box
        const bgColor = previewBox.getAttribute('data-bg-color') === 'true'

        // Create iframe content
        if (typeof window.PreviewManager !== 'undefined') {
          const iframeContent = window.PreviewManager.createIframeContent(
            htmlContent,
            cssContent,
            jsContent,
            theme,
            bgColor
          )
          modalIframe.srcdoc = iframeContent
        }
      } else {
        //modalIframe.src = externalSrc
      }

      let modalInstance = bootstrap.Modal.getInstance(modal)
      if (!modalInstance) {
        modalInstance = new bootstrap.Modal(modal, {
          backdrop: true,
          keyboard: true,
          focus: true
        })
      }

      modalInstance.show()

      setTimeout(() => {
        const activeDevice = previewBox.querySelector('.preview-devices .btn.active')
        if (activeDevice) {
          const width = activeDevice.dataset.width
          this.updatePreviewWidth(modal, width)
        }
      }, this.CONFIG.THEME_SYNC_DELAY)
    }

    if (modalIframe) {
      const onIframeLoad = function () {
        modalIframe.removeEventListener('load', onIframeLoad)
        showModalContent()
      }
      modalIframe.addEventListener('load', onIframeLoad)
    } else {
      showModalContent()
    }
  }

  static syncModalContent(previewBox, modal) {
    if (!previewBox || !modal) return

    // Check if using external source
    const externalSrc = previewBox.dataset.externalSrc
    if (!externalSrc) {
      // For non-external sources, proceed with full content sync
      // Sync HTML content
      const htmlEditor = window.CodeMirrorManager?.getEditorFromPreviewBox(previewBox, 'html')
      const modalHtmlEditor = window.CodeMirrorManager?.getEditorFromPreviewBox(modal, 'html')

      if (htmlEditor && modalHtmlEditor) {
        modalHtmlEditor.setValue(htmlEditor.getValue())
      }

      // Sync CSS content
      const cssEditor = window.CodeMirrorManager?.getEditorFromPreviewBox(previewBox, 'css')
      const modalCssEditor = window.CodeMirrorManager?.getEditorFromPreviewBox(modal, 'css')

      if (cssEditor && modalCssEditor) {
        modalCssEditor.setValue(cssEditor.getValue())
      }

      // Sync JS content
      const jsEditor = window.CodeMirrorManager?.getEditorFromPreviewBox(previewBox, 'javascript')
      const modalJsEditor = window.CodeMirrorManager?.getEditorFromPreviewBox(modal, 'javascript')

      if (jsEditor && modalJsEditor) {
        modalJsEditor.setValue(jsEditor.getValue())
      }

      // Sync background color - use getAttribute for consistency
      const bgColor = previewBox.getAttribute('data-bg-color')
      if (bgColor !== null) {
        modal.setAttribute('data-bg-color', bgColor)
      }
    }

    // Sync theme
    const themeToggle = previewBox.querySelector('.theme-toggle')
    const modalThemeToggle = modal.querySelector('.theme-toggle')

    if (themeToggle && modalThemeToggle) {
      const theme = themeToggle.dataset.currentTheme || 'light'
      modalThemeToggle.dataset.currentTheme = theme

      const icon = modalThemeToggle.querySelector('i')
      if (icon) {
        this.updateThemeIcon(icon, theme)
      }

      // Sync data-bs-theme between card-body and modal-body
      const cardBody = previewBox.querySelector('.card-body')
      const modalBody = modal.querySelector('.modal-body')

      if (cardBody && modalBody) {
        // Get the theme from the card-body or default to the toggle value
        const cardBodyTheme = cardBody.getAttribute('data-bs-theme') || theme
        modalBody.setAttribute('data-bs-theme', cardBodyTheme)
      }
    }
  }

  static syncModalDeviceWidth(previewBox, modal) {
    const activeDevice = previewBox.querySelector('.preview-devices .btn.active')
    if (activeDevice) {
      const width = activeDevice.dataset.width
      const modalContainer = modal.querySelector('.preview-container')
      if (modalContainer) {
        modalContainer.style.maxWidth = '100%'
        modalContainer.style.width = width === '100%' ? '100%' : `${width}px`
        modalContainer.style.margin = width === '100%' ? '0' : '0 auto'
      }

      const modalDevices = modal.querySelector('.preview-devices')
      if (modalDevices) {
        modalDevices.querySelectorAll('.btn').forEach((btn) => {
          btn.classList.toggle('active', btn.dataset.width === width)
          btn.setAttribute('aria-pressed', btn.dataset.width === width)
        })
      }
    }
  }

  static setupDownloadButtons() {
    document.querySelectorAll('.download-button').forEach((button) => {
      // Remove any existing event listeners by cloning and replacing
      const newButton = button.cloneNode(true)
      button.parentNode.replaceChild(newButton, button)

      newButton.addEventListener('click', () => {
        const format = newButton.getAttribute('data-format') || 'zip'
        const previewBox =
          newButton.closest('.preview-box') ||
          newButton.closest('.preview-modal') ||
          newButton.closest('.card')?.closest('.preview-box') ||
          newButton.closest('.card')?.closest('.preview-modal')

        if (previewBox) {
          console.log(`Downloading in ${format} format from UIControlsManager`)
          window.CodeMirrorManager.downloadCode(previewBox, format)
        } else {
          console.error('Could not find preview box for download')
        }
      })
    })
  }

  static setupKeyboardShortcuts() {
    if (!this.CONFIG.KEYBOARD_SHORTCUTS) return

    document.addEventListener('keydown', (e) => {
      // Global shortcuts
      if (e.ctrlKey || e.metaKey) {
        // Ctrl+Shift+E: Toggle edit mode
        if (e.shiftKey && e.key === 'E') {
          const activeElement = document.activeElement
          const previewBox =
            activeElement.closest('.preview-box') || activeElement.closest('.preview-modal')
          if (previewBox) {
            const editButton = previewBox.querySelector('.edit-button')
            if (editButton) {
              editButton.click()
              e.preventDefault()
            }
          }
        }

        // Ctrl+Shift+R: Reset code
        if (e.shiftKey && e.key === 'R') {
          const activeElement = document.activeElement
          const previewBox =
            activeElement.closest('.preview-box') || activeElement.closest('.preview-modal')
          if (previewBox) {
            const resetButton = previewBox.querySelector('.reset-all-button')
            if (resetButton) {
              resetButton.click()
              e.preventDefault()
            }
          }
        }

        // Ctrl+Shift+D: Download code
        if (e.shiftKey && e.key === 'D') {
          const activeElement = document.activeElement
          const previewBox =
            activeElement.closest('.preview-box') || activeElement.closest('.preview-modal')
          if (previewBox) {
            window.CodeMirrorManager.downloadCode(previewBox, 'zip')
            e.preventDefault()
          }
        }
      }
    })
  }

  static setupAccessibility() {
    // Add focus indicators for keyboard navigation
    const style = document.createElement('style')
    style.textContent = `
      .preview-box button:focus-visible,
      .preview-modal button:focus-visible {
        outline: 2px solid #0d6efd;
        outline-offset: 2px;
      }

      .codemirror-editor-container:focus-within {
        outline: 2px solid #0d6efd;
      }

      .edit-mode-indicator {
        pointer-events: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        transition: opacity 0.3s ease;
      }

      .codemirror-editor-container {
        position: relative;
      }
    `
    document.head.appendChild(style)

    // Add aria attributes to interactive elements
    document.querySelectorAll('.preview-devices .btn').forEach((btn) => {
      btn.setAttribute('aria-pressed', btn.classList.contains('active'))
    })

    document.querySelectorAll('.code-toggle-link').forEach((btn) => {
      btn.setAttribute('aria-expanded', btn.classList.contains('active'))
    })
  }
}
