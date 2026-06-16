/* global HTMLElement */

export type FileNode = {
  name: string
  type: 'folder' | 'file'
  size?: string
  modified?: string
  icon?: string
  children?: FileNode[]
}

const DEFAULT_FS: FileNode = {
  name: 'Root',
  type: 'folder',
  children: [
    {
      name: 'Documents',
      type: 'folder',
      modified: '2026-06-10',
      children: [
        { name: 'Project Proposal.pdf', type: 'file', size: '2.4 MB', modified: '2026-06-08' },
        { name: 'Meeting Notes.docx', type: 'file', size: '156 KB', modified: '2026-06-09' },
        { name: 'Budget 2026.xlsx', type: 'file', size: '890 KB', modified: '2026-06-10' },
        {
          name: 'Reports',
          type: 'folder',
          modified: '2026-06-05',
          children: [
            { name: 'Q1 Report.pdf', type: 'file', size: '3.1 MB', modified: '2026-04-01' },
            { name: 'Q2 Report.pdf', type: 'file', size: '2.8 MB', modified: '2026-06-05' }
          ]
        }
      ]
    },
    {
      name: 'Images',
      type: 'folder',
      modified: '2026-06-12',
      children: [
        { name: 'logo.png', type: 'file', size: '45 KB', modified: '2026-05-20' },
        { name: 'banner.jpg', type: 'file', size: '1.2 MB', modified: '2026-06-12' },
        { name: 'avatar.svg', type: 'file', size: '8 KB', modified: '2026-06-01' }
      ]
    },
    {
      name: 'Downloads',
      type: 'folder',
      modified: '2026-06-15',
      children: [
        { name: 'installer.exe', type: 'file', size: '45.2 MB', modified: '2026-06-15' },
        { name: 'archive.zip', type: 'file', size: '12.8 MB', modified: '2026-06-14' }
      ]
    },
    {
      name: 'Videos',
      type: 'folder',
      modified: '2026-06-01',
      children: [
        { name: 'presentation.mp4', type: 'file', size: '128 MB', modified: '2026-06-01' }
      ]
    },
    { name: 'readme.txt', type: 'file', size: '4 KB', modified: '2026-01-15' },
    { name: 'config.json', type: 'file', size: '1 KB', modified: '2026-03-22' }
  ]
}

function getFileIcon(node: FileNode): string {
  if (node.type === 'folder') return 'ri-folder-fill text-warning'
  const ext = node.name.split('.').pop()?.toLowerCase() || ''
  const iconMap: Record<string, string> = {
    pdf: 'ri-file-pdf-2-fill text-danger',
    doc: 'ri-file-word-fill text-primary',
    docx: 'ri-file-word-fill text-primary',
    xls: 'ri-file-excel-fill text-success',
    xlsx: 'ri-file-excel-fill text-success',
    png: 'ri-image-fill text-info',
    jpg: 'ri-image-fill text-info',
    jpeg: 'ri-image-fill text-info',
    svg: 'ri-image-fill text-info',
    zip: 'ri-file-zip-fill text-secondary',
    rar: 'ri-file-zip-fill text-secondary',
    mp4: 'ri-video-fill text-purple',
    mp3: 'ri-music-fill text-pink',
    exe: 'ri-settings-fill text-muted',
    json: 'ri-code-s-slash-fill text-warning',
    txt: 'ri-file-text-fill text-muted'
  }
  return iconMap[ext] || 'ri-file-fill text-muted'
}

interface FileManagerState {
  root: FileNode
  currentPath: string[]
  viewMode: 'grid' | 'list'
  expandedFolders: Set<string>
}

function resolveFolder(root: FileNode, path: string[]): FileNode {
  let node = root
  for (const seg of path) {
    const child = node.children?.find((c) => c.name === seg && c.type === 'folder')
    if (!child) break
    node = child
  }
  return node
}

function getPathKey(path: string[]): string {
  return path.join('/')
}

function renderTree(
  node: FileNode,
  state: FileManagerState,
  path: string[]
): string {
  if (node.type !== 'folder') return ''
  const currentKey = getPathKey(path)
  const isExpanded = state.expandedFolders.has(currentKey)
  const isActive = getPathKey(state.currentPath) === currentKey
  const hasChildren = node.children?.some((c) => c.type === 'folder') || false
  const chevron = hasChildren
    ? `<i class="ri-arrow-right-s-line tree-chevron ${isExpanded ? 'rotate-90' : ''}"></i>`
    : '<span style="width:16px;display:inline-block"></span>'

  let html = `<div class="tree-item${isActive ? ' active' : ''}" data-tree-path="${currentKey}">
    ${chevron}
    <i class="ri-folder-fill text-warning me-1"></i>
    <span class="tree-label">${node.name}</span>
  </div>`

  if (isExpanded && node.children) {
    const folders = node.children.filter((c) => c.type === 'folder')
    if (folders.length > 0) {
      html += '<div class="tree-children">'
      for (const child of folders) {
        html += renderTree(child, state, [...path, child.name])
      }
      html += '</div>'
    }
  }
  return html
}

function renderBreadcrumb(path: string[]): string {
  let html = '<nav aria-label="File path"><ol class="breadcrumb mb-0">'
  html += `<li class="breadcrumb-item"><a href="#" data-breadcrumb-index="-1"><i class="ri-home-4-line"></i> Root</a></li>`
  path.forEach((seg, i) => {
    const isLast = i === path.length - 1
    if (isLast) {
      html += `<li class="breadcrumb-item active">${seg}</li>`
    } else {
      html += `<li class="breadcrumb-item"><a href="#" data-breadcrumb-index="${i}">${seg}</a></li>`
    }
  })
  html += '</ol></nav>'
  return html
}

function renderGridView(items: FileNode[]): string {
  if (items.length === 0) return '<div class="text-muted p-4 text-center">This folder is empty</div>'
  let html = '<div class="row g-3">'
  for (const item of items) {
    const icon = getFileIcon(item)
    html += `<div class="col-xl-2 col-lg-3 col-md-4 col-sm-6">
      <div class="card file-item text-center p-3 h-100" data-file-name="${item.name}" data-file-type="${item.type}" role="button">
        <div class="mb-2"><i class="${icon}" style="font-size:2.5rem"></i></div>
        <div class="text-truncate fw-medium small">${item.name}</div>
        ${item.size ? `<div class="text-muted" style="font-size:0.75rem">${item.size}</div>` : ''}
      </div>
    </div>`
  }
  html += '</div>'
  return html
}

function renderListView(items: FileNode[]): string {
  if (items.length === 0) return '<div class="text-muted p-4 text-center">This folder is empty</div>'
  let html = `<div class="table-responsive"><table class="table table-hover align-middle mb-0">
    <thead><tr>
      <th>Name</th><th>Size</th><th>Modified</th><th>Type</th>
    </tr></thead><tbody>`
  for (const item of items) {
    const icon = getFileIcon(item)
    const ext = item.type === 'folder' ? 'Folder' : (item.name.split('.').pop()?.toUpperCase() || 'File')
    html += `<tr class="file-item" data-file-name="${item.name}" data-file-type="${item.type}" role="button">
      <td><i class="${icon} me-2"></i>${item.name}</td>
      <td>${item.size || '--'}</td>
      <td>${item.modified || '--'}</td>
      <td>${ext}</td>
    </tr>`
  }
  html += '</tbody></table></div>'
  return html
}

export function initFileManager() {
  document.querySelectorAll<HTMLElement>('.file-manager:not([data-inited])').forEach((container) => {
    container.dataset.inited = 'true'

    let rootData: FileNode
    try {
      rootData = JSON.parse(container.dataset.rootFolder || '{}')
      if (!rootData.name) rootData = DEFAULT_FS
    } catch {
      rootData = DEFAULT_FS
    }

    const state: FileManagerState = {
      root: rootData,
      currentPath: [],
      viewMode: 'grid',
      expandedFolders: new Set<string>([''])
    }

    const treeEl = container.querySelector<HTMLElement>('.fm-tree')
    const contentEl = container.querySelector<HTMLElement>('.fm-content')
    const breadcrumbEl = container.querySelector<HTMLElement>('.fm-breadcrumb')
    const gridBtn = container.querySelector<HTMLElement>('[data-view="grid"]')
    const listBtn = container.querySelector<HTMLElement>('[data-view="list"]')

    if (!treeEl || !contentEl || !breadcrumbEl) return

    function render() {
      // Render tree
      treeEl!.innerHTML = renderTree(state.root, state, [])

      // Render breadcrumb
      breadcrumbEl!.innerHTML = renderBreadcrumb(state.currentPath)

      // Render content
      const folder = resolveFolder(state.root, state.currentPath)
      const items = folder.children || []
      contentEl!.innerHTML = state.viewMode === 'grid'
        ? renderGridView(items)
        : renderListView(items)

      // Update view toggle buttons
      gridBtn?.classList.toggle('active', state.viewMode === 'grid')
      listBtn?.classList.toggle('active', state.viewMode === 'list')

      bindEvents()
    }

    function navigateTo(path: string[]) {
      state.currentPath = path
      // Auto-expand parents
      for (let i = 0; i <= path.length; i++) {
        state.expandedFolders.add(getPathKey(path.slice(0, i)))
      }
      render()
    }

    function bindEvents() {
      // Tree click
      treeEl!.querySelectorAll<HTMLElement>('.tree-item').forEach((el) => {
        el.addEventListener('click', (e) => {
          e.preventDefault()
          e.stopPropagation()
          const pathStr = el.dataset.treePath || ''
          const path = pathStr ? pathStr.split('/') : []

          // Toggle expand
          const key = getPathKey(path)
          if (state.expandedFolders.has(key)) {
            // Only collapse if not navigating to it
            if (getPathKey(state.currentPath) === key) {
              state.expandedFolders.delete(key)
            }
          } else {
            state.expandedFolders.add(key)
          }

          navigateTo(path)
        })
      })

      // File/folder click in content
      contentEl!.querySelectorAll<HTMLElement>('.file-item').forEach((el) => {
        el.addEventListener('click', () => {
          if (el.dataset.fileType === 'folder') {
            navigateTo([...state.currentPath, el.dataset.fileName || ''])
          }
        })
      })

      // Breadcrumb click
      breadcrumbEl!.querySelectorAll<HTMLElement>('[data-breadcrumb-index]').forEach((el) => {
        el.addEventListener('click', (e) => {
          e.preventDefault()
          const idx = parseInt(el.dataset.breadcrumbIndex || '-1', 10)
          navigateTo(idx < 0 ? [] : state.currentPath.slice(0, idx + 1))
        })
      })
    }

    // View toggle
    gridBtn?.addEventListener('click', () => {
      state.viewMode = 'grid'
      render()
    })

    listBtn?.addEventListener('click', () => {
      state.viewMode = 'list'
      render()
    })

    render()
  })
}
