/**
 * Get the CSS file path based on development mode
 * @param {boolean} isDev - Whether in development mode
 * @returns {string} CSS file path
 */
export function getCSS(isDev) {
  return isDev ? `/dist/css/style.css` : `/css/style.min.css`
}

export function getSkinCSS(isDev) {
  return isDev ? `/dist/assets/vendor/css/skin.css` : `/assets/vendor/css/skin.css`
}
/**
 * Get the JavaScript file path based on filename and development mode
 * @param {string} filename - The JavaScript file name
 * @param {boolean} isDev - Whether in development mode
 * @returns {string} JavaScript file path
 */
export function getJS(filename, isDev) {
  return isDev ? `/dist/js/${filename}.js` : `/js/${filename}.min.js`
}

/**
 * Generate a unique preview ID
 * @returns {string} Generated preview ID
 */
export function generatePreviewId() {
  return `preview-${Math.random().toString(36).substr(2, 9)}`
}

/**
 * @typedef {Object} IframeContentProps
 * @property {boolean} bgColor - Whether to use a background color
 * @property {string} component - The component HTML
 * @property {string} [cssCode] - Optional CSS code
 * @property {string} [jsCode] - Optional JavaScript code
 * @property {boolean} isDev - Whether in development mode
 */

/**
 * Create the iframe content
 * @param {IframeContentProps} props - The iframe content properties
 * @returns {string} Generated iframe HTML content
 */
export function createIframeContent({ bgColor, component, cssCode, jsCode, isDev }) {
  // Set the background color based on the bgColor prop
  const backgroundColor = bgColor ? 'var(--content-wrapper-bg)' : 'transparent'
  return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <script>
    const theme = localStorage.getItem("theme");
    if (theme) {
      localStorage.setItem("iframe-theme", theme);
      document.documentElement.setAttribute("data-bs-theme", theme);
    }
  </script>

  <link href="${getCSS(isDev)}" rel="stylesheet">
  <link href="${getSkinCSS(isDev)}" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/remixicon@4.6.0/fonts/remixicon.css" rel="stylesheet">

  <!-- Source Sans 3 from Google Fonts -->
  <link
    href="https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,200..900;1,200..900&family=Ubuntu+Mono:ital,wght@0,400;0,700;1,400;1,700&display=swap"
    rel="stylesheet"
  />

  <style id="component-style">
    body {
      padding: 1rem;
      margin: 0;
      background-color: ${backgroundColor};
    }
    #component-wrapper {
      width: 100%;
      height: 100%;
      position: relative;
    }
    #component-html {
      width: 100%;
      height: 100%;
    }
  </style>

  <style id="custom-css">
    ${cssCode || ''}
  </style>

  <script>
    window.addEventListener('message', function(event) {
      if (event.data && event.data.type === 'setTheme') {
        document.documentElement.setAttribute('data-bs-theme', event.data.theme);
        document.body.classList.remove('theme-update');
        void document.body.offsetWidth;
        document.body.classList.add('theme-update');
        window.parent.postMessage({ type: 'themeAcknowledged', theme: event.data.theme }, '*');
      } else if (event.data && event.data.type === 'updateContent') {
        if (event.data.html !== undefined) {
          document.getElementById('component-html').innerHTML = event.data.html;
        }

        if (event.data.css !== undefined) {
          const styleTag = document.getElementById('custom-css');
          if (styleTag) {
            styleTag.textContent = event.data.css;
          }
        }

        if (event.data.js !== undefined) {
          try {
            const oldScript = document.getElementById('custom-js');
            if (oldScript) {
              oldScript.remove();
            }
            const newScript = document.createElement('script');
            newScript.id = 'custom-js';
            newScript.textContent = event.data.js;
            document.body.appendChild(newScript);
            (new Function(event.data.js))();
          } catch (error) {
            console.error('Error executing JavaScript:', error);
          }
        }
        window.parent.postMessage({ type: 'contentAcknowledged' }, '*');
      }
    });

    window.parent.postMessage({
      type: 'iframeReady',
      theme: document.documentElement.getAttribute('data-bs-theme')
    }, '*');
  </script>
</head>
<body>
  <div id="component-wrapper">
    <div id="component-html">
      ${component}
    </div>
  </div>

  <script src="${getJS('main', isDev)}" type="module"></script>

  <div id="custom-js">
    ${jsCode || ''}
  </div>
</body>
</html>
`
}
