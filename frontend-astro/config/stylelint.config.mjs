/** @type {import("stylelint").Config} */
export default {
  extends: [
    'stylelint-config-standard-scss',
    'stylelint-config-recommended',
    'stylelint-config-twbs-bootstrap'
  ],
  plugins: [
    '@stylistic/stylelint-plugin'
  ],
  rules: {
    '@stylistic/value-list-comma-newline-after': 'always-multi-line',
    '@stylistic/value-list-comma-space-after': 'always-single-line',
    '@stylistic/indentation': 2,
    '@stylistic/string-quotes': 'single',
    '@stylistic/no-eol-whitespace': true,
    '@stylistic/number-leading-zero': 'always',
    'scss/load-partial-extension': null,
    'no-descending-specificity': null,
    'selector-class-pattern': null,
    'selector-no-vendor-prefix': null,
    'property-no-vendor-prefix': null
  },
  reportInvalidScopeDisables: true,
  reportNeedlessDisables: true,
  ignoreFiles: [
    "**/*.html",
    "**/*.md",
    "**/*.min.css",
    "**/.temp/",
    "**/dist/",
    "**/docs_html/",
    "**/plugins/",
    "**/.cache/"
  ],
  overrides: [
    {
      files: ['**/*.scss'],
      rules: {
        'declaration-no-important': null,
        'declaration-property-value-disallowed-list': {
          border: 'none',
          outline: 'none'
        },
        'function-disallowed-list': [
          'calc',
          'lighten',
          'darken'
        ],
        'keyframes-name-pattern': null,
        'scss/dollar-variable-default': [
          true,
          {
            ignore: 'local'
          }
        ],
        'scss/selector-no-union-class-name': true,
        'selector-max-class': null,
        'selector-max-combinators': null,
        'selector-max-compound-selectors': null,
        'selector-max-id': null,
        'selector-max-specificity': null,
        'selector-max-type': null,
        'selector-no-qualifying-type': null
      }
    }
  ]
}
