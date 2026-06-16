/* global CodeMirror */

// CodeMirror Editor Configuration and Management
window.CodeMirrorConfig = {
  EDITOR_DEFAULTS: {
    lineNumbers: true,
    lineWrapping: true,
    tabSize: 2,
    indentWithTabs: false,
    readOnly: true,
    theme: 'base16-dark',
    autoCloseBrackets: true,
    autoCloseTags: true,
    matchBrackets: true,
    matchTags: true,
    scrollbarStyle: 'native',
    viewportMargin: Infinity
  }
}

// Ensure we have access to the CodeMirrorManager class globally
window.CodeMirrorManager = class CodeMirrorEditorSystem {
  // Initialization state tracking
  static initialized = false
  static editors = new Map()

  // CodeMirror initialization
  static async initializeCodeMirror() {
    if (this.initialized) {
      return Promise.resolve()
    }

    return new Promise((resolve) => {
      // Check if CodeMirror is available
      if (typeof window.CodeMirror === 'undefined') {
        console.error('CodeMirror is not available')
        this.showFallbackEditors()
        resolve()
        return
      }

      // Initialize editors since CodeMirror is available
      this.initialized = true
      this.initializeEditors()
      resolve()
    })
  }

  // Editor initialization and management
  static initializeEditors() {
    document.querySelectorAll('.codemirror-editor-container').forEach((container) => {
      if (container.editor) return

      const editorLanguage = container.dataset.language
      const defaultCode = container.dataset.code || ''

      try {
        // Map language to CodeMirror mode
        const mode = this.getCodeMirrorMode(editorLanguage)

        // Create editor
        const editor = CodeMirror(container, {
          value: defaultCode,
          mode: mode,
          ...window.CodeMirrorConfig.EDITOR_DEFAULTS
        })

        // Store editor reference
        container.editor = editor
        container.defaultCode = defaultCode
        this.editors.set(container, editor)

        // Force immediate refresh to ensure proper rendering
        setTimeout(() => {
          editor.refresh()
        }, 0)

        // Add change event listener for basic functionality
        editor.on('change', () => {
          if (typeof window.PreviewManager !== 'undefined') {
            window.PreviewManager.handleContentChange(editor, container)
          }
        })
      } catch (error) {
        console.error('CodeMirror editor initialization failed:', error)
        this.createFallbackEditor(container, defaultCode)
      }
    })
  }

  // Map language to CodeMirror mode
  static getCodeMirrorMode(language) {
    const modeMap = {
      html: 'htmlmixed',
      css: 'css',
      javascript: 'javascript',
      js: 'javascript',
      json: { name: 'javascript', json: true },
      typescript: { name: 'javascript', typescript: true },
      xml: 'xml',
      markdown: 'markdown',
      php: 'php',
      python: 'python',
      ruby: 'ruby',
      sql: 'sql'
    }

    return modeMap[language] || 'text/plain'
  }

  // Fallback editor creation
  static createFallbackEditor(container, defaultCode) {
    const pre = document.createElement('pre')
    pre.className = 'p-3 bg-dark text-light rounded'
    pre.style.maxHeight = '300px'
    pre.style.overflow = 'auto'

    const code = document.createElement('code')
    code.textContent = defaultCode
    pre.appendChild(code)

    container.innerHTML = ''
    container.appendChild(pre)
  }

  static showFallbackEditors() {
    document.querySelectorAll('.codemirror-editor-container').forEach((container) => {
      if (container.editor) return

      const defaultCode = container.dataset.code || ''
      this.createFallbackEditor(container, defaultCode)
    })
  }

  // Utility methods for editor access and code download
  static getEditorFromPreviewBox(previewBox, editorLanguage) {
    const container = previewBox.querySelector(
      `.codemirror-editor-container[data-language="${editorLanguage}"]`
    )
    return container?.editor
  }

  static downloadCode(previewBox, format = 'zip') {
    if (!previewBox) return

    const htmlEditor = this.getEditorFromPreviewBox(previewBox, 'html')
    const cssEditor = this.getEditorFromPreviewBox(previewBox, 'css')
    const jsEditor = this.getEditorFromPreviewBox(previewBox, 'javascript')

    const htmlContent = htmlEditor ? htmlEditor.getValue() : ''
    const cssContent = cssEditor ? cssEditor.getValue() : ''
    const jsContent = jsEditor ? jsEditor.getValue() : ''

    // Get bgColor from preview box data attribute - use getAttribute for consistency
    const bgColor = previewBox.getAttribute('data-bg-color') === 'true'

    // Get the current theme
    const themeToggle = previewBox.querySelector('.theme-toggle')
    const theme = themeToggle?.dataset.currentTheme || 'light'

    // Create the full HTML content
    let fullHTML = `<!DOCTYPE html>
<html data-bs-theme="${theme}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Component</title>
  <link href="https://cdn.jsdelivr.net/npm/asteroadmin@latest/dist/css/style.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/remixicon@4.6.0/fonts/remixicon.css" rel="stylesheet">
  <!-- Source Sans 3 from Google Fonts -->
  <link
    href="https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,200..900;1,200..900&family=Ubuntu+Mono:ital,wght@0,400;0,700;1,400;1,700&display=swap"
    rel="stylesheet"
  />
  <style>
    html, body {
      padding: 0;
      margin: 0;
      background-color: ${bgColor ? 'var(--content-wrapper-bg)' : 'transparent'};
    }
    .component-wrapper {
      padding: 1rem;
    }
  </style>
  ${cssContent ? '<style>\n' + cssContent + '\n</style>' : ''}
</head>
<body>
  <div class="component-wrapper">
    ${htmlContent}
  </div>
  ${jsContent ? '<script>\n' + jsContent + '\n</script>' : ''}
  <script src="https://cdn.jsdelivr.net/npm/asteroadmin@latest/dist/js/main.min.js" type="module"></script>
</body>
</html>`

    if (format === 'zip' && typeof window.JSZip !== 'undefined') {
      // Download as ZIP file
      const zip = new window.JSZip()
      zip.file('index.html', fullHTML)
      if (cssContent) zip.file('styles.css', cssContent)
      if (jsContent) zip.file('script.js', jsContent)

      // Generate and download the zip
      zip.generateAsync({ type: 'blob' }).then(function (content) {
        const url = window.URL.createObjectURL(content)
        const a = document.createElement('a')
        a.href = url
        a.download = 'component.zip'
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        window.URL.revokeObjectURL(url)
      })
    } else {
      // Download as HTML file
      const blob = new window.Blob([fullHTML], { type: 'text/html' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'component.html'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    }
  }

  // Main initialization
  static init() {
    // Use a flag to track if we've already initialized
    if (window.codeMirrorInitialized) {
      return
    }
    window.codeMirrorInitialized = true

    // Handle tab changes to ensure editors are properly refreshed
    document.addEventListener(
      'shown.bs.tab',
      (event) => {
        const tabPane = document.querySelector(event.target.getAttribute('data-bs-target'))
        if (tabPane) {
          const editor = tabPane.querySelector('.codemirror-editor-container')?.editor
          if (editor) {
            editor.refresh()
          }
        }
      },
      { passive: true }
    )

    // Add basic styles
    const style = document.createElement('style')
    style.textContent = `
      .codemirror-editor-container {
        position: relative;
        min-height: 150px;
      }

      /* CodeMirror theme overrides */
      .CodeMirror {
        height: auto !important;
        min-height: 150px;
        border-radius: 4px;
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
        font-size: 14px;
        line-height: 1.5;
      }
    `
    document.head.appendChild(style)

    // Initialize CodeMirror
    try {
      this.initializeCodeMirror()
        .then(() => {
          this.setupDownloadButtons()
        })
        .catch((error) => {
          console.error('CodeMirror initialization failed:', error)
          this.showFallbackEditors()
        })
    } catch (error) {
      console.error('Error during CodeMirror initialization:', error)
      this.showFallbackEditors()
    }
  }

  static setupDownloadButtons() {
    document.querySelectorAll('.download-button').forEach((button) => {
      button.addEventListener(
        'click',
        () => {
          const previewBox = button.closest('.preview-box') || button.closest('.preview-modal')
          if (previewBox) {
            window.CodeMirrorManager.downloadCode(previewBox, 'zip')
          }
        },
        { passive: true }
      )
    })
  }
}

// Initialize
window.CodeMirrorManager.init()

// Set up download buttons when DOM is loaded
document.addEventListener(
  'DOMContentLoaded',
  () => {
    window.CodeMirrorManager.setupDownloadButtons()
  },
  { passive: true }
)
