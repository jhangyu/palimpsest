// Import necessary ESLint configurations
import js from '@eslint/js'
import tsParser from '@typescript-eslint/parser'
import tsPlugin from '@typescript-eslint/eslint-plugin'
import astroParser from 'astro-eslint-parser'
import astroPlugin from 'eslint-plugin-astro'

export default [
  {
    ignores: [
      '**/node_modules/',
      '.astro/**/*',
      '.cache/**/*',
      '.git/',
      'dist/**/*', // ignore all contents in dist directory
      '!dist/**/*/', // unignore subdirectories for traversal
      '**/*.min.js',
      '.temp/**/*',
      '**/env.d.ts'
    ]
  },

  // Base JS config
  js.configs.recommended,

  // Astro files configuration
  {
    files: ['**/*.astro'],
    plugins: {
      astro: astroPlugin
    },
    languageOptions: {
      parser: astroParser,
      parserOptions: {
        parser: tsParser,
        extraFileExtensions: ['.astro'],
        sourceType: 'module'
      }
    },
    rules: {
      ...astroPlugin.configs.recommended.rules,
      'astro/no-conflict-set-directives': 'error',
      'astro/no-unused-define-vars-in-style': 'error'
    }
  },

  // TypeScript files configuration
  {
    files: ['**/*.ts', '**/*.tsx'],
    plugins: {
      '@typescript-eslint': tsPlugin
    },
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        project: './tsconfig.json',
        ecmaVersion: 'latest',
        sourceType: 'module'
      }
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/no-unused-vars': 'warn'
    }
  },

  // Browser environment and globals
  {
    languageOptions: {
      // Add browser globals to fix the 'no-undef' errors for document, window, etc.
      globals: {
        document: 'readonly',
        window: 'readonly',
        console: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        localStorage: 'readonly',
        sessionStorage: 'readonly',
        navigator: 'readonly',
        location: 'readonly',
        history: 'readonly',
        $: 'readonly',
        jQuery: 'readonly',
        bootstrap: 'readonly',
        DataTable: 'readonly',
        monaco: 'readonly',
        confirm: 'readonly',
        alert: 'readonly',
        process: 'readonly',
        Buffer: 'readonly',
        require: 'readonly',
        module: 'readonly',
        exports: 'readonly',
        __dirname: 'readonly',
        __filename: 'readonly',
        performance: 'readonly',
        self: 'readonly',
        define: 'readonly'
      },
      ecmaVersion: 'latest',
      sourceType: 'module'
    },
    rules: {
      semi: ['error', 'never'],
      'comma-dangle': ['error', 'never'],
      indent: 'off', // Let Prettier handle indentation
      'object-curly-spacing': ['error', 'always'],
      'no-console': 'off',
      'no-undef': 'error',
      'no-unused-vars': 'warn',
      'no-redeclare': 'warn',
      'no-useless-escape': 'warn',
      'no-empty': 'warn'
    }
  },

  // Config specific overrides
  {
    files: ['./config/**'],
    rules: {
      'no-console': 'off'
    }
  }
]
