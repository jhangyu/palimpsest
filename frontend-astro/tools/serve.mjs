import express from 'express'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'
import chalk from 'chalk'
import fs from 'fs'
import open from 'open'
import { createServer } from 'http'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const app = express()
const startPort = process.env.PORT || 3000
let currentPort = startPort
const DIST_DIR = join(__dirname, '../dist')

// Custom middleware to handle URLs without .html extension
app.use((req, res, next) => {
  if (req.path.endsWith('/')) {
    // Check if index.html exists in the directory
    const indexPath = join(DIST_DIR, req.path, 'index.html')
    if (fs.existsSync(indexPath)) {
      req.url = join(req.path, 'index.html')
    }
  } else if (!req.path.includes('.')) {
    // If path has no extension, check if .html version exists
    const htmlPath = join(DIST_DIR, `${req.path}.html`)
    if (fs.existsSync(htmlPath)) {
      req.url = `${req.path}.html`
    }
  }
  next()
})

// Serve static files from dist directory
app.use(express.static(DIST_DIR))

// Handle all routes by serving index.html for non-existent paths
app.get('*', (req, res) => {
  res.sendFile(join(DIST_DIR, 'index.html'))
})

// Function to try starting server with auto port increment if needed
function startServer(port) {
  const server = createServer(app)

  server.on('error', (error) => {
    if (error.code === 'EADDRINUSE') {
      console.log(chalk.yellow(`Port ${port} is already in use, trying port ${port + 1}`))
      currentPort = port + 1
      startServer(currentPort)
    } else {
      console.error('Server error:', error)
    }
  })

  server.listen(port, async () => {
    console.log(chalk.green(`✓ Server running at http://localhost:${port}`))
    console.log(chalk.blue('  Serving files from: dist/'))

    // Open dashboard in default browser
    try {
      await open(`http://localhost:${port}/pages/dashboard`)
      console.log(chalk.green('✓ Dashboard opened in your default browser'))
    } catch {
      console.log(chalk.yellow('! Could not automatically open the browser'))
    }
  })
}

// Start the server
startServer(currentPort)
