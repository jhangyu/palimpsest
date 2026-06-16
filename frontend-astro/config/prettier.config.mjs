/** @type {import("prettier").Config} */
export default {
  plugins: ['prettier-plugin-astro'],
  semi: false,
  singleQuote: true,
  printWidth: 100,
  tabWidth: 2,
  trailingComma: 'none',
  overrides: [
    {
      files: '*.astro',
      options: {
        parser: 'astro'
      }
    }
  ],
  // Only format specific file types, let ESLint handle JS/TS
  ignorePatterns: [
    // Dependencies and build files
    'node_modules/**',
    'dist/**',
    '.cache/**',
    '.astro/**'
  ]
}
