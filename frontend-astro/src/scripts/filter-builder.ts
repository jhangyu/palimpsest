import type { FilterConfig, FilterRule, FilterGroup } from './api'
import { escapeAttr } from '@/scripts/utils'

// ---------------------------------------------------------------------------
// Internal state
// ---------------------------------------------------------------------------
let _root: HTMLElement | null = null
let _config: FilterConfig | null = null

// ---------------------------------------------------------------------------
// ID generator
// ---------------------------------------------------------------------------
function uid(): string {
  return Math.random().toString(36).slice(2, 9)
}

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------
export function createDefaultFilterConfig(): FilterConfig {
  return {
    mode: 'blacklist',
    match_whole_word: false,
    root: { id: uid(), type: 'group', operator: 'and', children: [] }
  }
}

function mkRule(): FilterRule {
  return { id: uid(), type: 'rule', field: 'title', match: 'contains', value: '' }
}

function mkGroup(): FilterGroup {
  return { id: uid(), type: 'group', operator: 'and', children: [] }
}

// ---------------------------------------------------------------------------
// Tree helpers
// ---------------------------------------------------------------------------
function findGroup(node: FilterGroup, id: string): FilterGroup | null {
  if (node.id === id) return node
  for (const child of node.children) {
    if (child.type === 'group') {
      const found = findGroup(child as FilterGroup, id)
      if (found) return found
    }
  }
  return null
}

function findRule(node: FilterGroup, id: string): FilterRule | null {
  for (const child of node.children) {
    if (child.type === 'rule' && child.id === id) return child as FilterRule
    if (child.type === 'group') {
      const found = findRule(child as FilterGroup, id)
      if (found) return found
    }
  }
  return null
}

function findParentOf(node: FilterGroup, id: string): FilterGroup | null {
  for (const child of node.children) {
    if (child.id === id) return node
    if (child.type === 'group') {
      const found = findParentOf(child as FilterGroup, id)
      if (found) return found
    }
  }
  return null
}

function moveItem(parentId: string, itemId: string, dir: -1 | 1): void {
  if (!_config) return
  const parent = findGroup(_config.root, parentId)
  if (!parent) return
  const idx = parent.children.findIndex((c) => c.id === itemId)
  if (idx < 0) return
  const newIdx = idx + dir
  if (newIdx < 0 || newIdx >= parent.children.length) return
  const [item] = parent.children.splice(idx, 1)
  parent.children.splice(newIdx, 0, item)
  render()
}

// ---------------------------------------------------------------------------
// Render helpers
// ---------------------------------------------------------------------------
const FIELD_OPTS: [string, string][] = [
  ['title', 'Title'],
  ['content', 'Content'],
  ['title_content', 'Title & Content']
]

const MATCH_OPTS: [string, string][] = [
  ['contains', 'Contains'],
  ['not_contains', 'Not Contains'],
  ['equals', 'Equals'],
  ['starts_with', 'Starts With'],
  ['ends_with', 'Ends With'],
  ['regex', 'Regex']
]

function optionsHtml(opts: [string, string][], selected: string): string {
  return opts
    .map(([v, l]) => `<option value="${v}"${selected === v ? ' selected' : ''}>${l}</option>`)
    .join('')
}

function renderRule(
  rule: FilterRule,
  index: number,
  total: number,
  parentId: string
): string {
  const upDisabled = index === 0 ? ' disabled' : ''
  const downDisabled = index === total - 1 ? ' disabled' : ''
  return `
    <div class="d-flex align-items-center gap-1 mb-1 flex-wrap" data-rule-id="${rule.id}">
      <select class="form-select form-select-sm" style="width:auto"
        data-action="update-rule-field" data-rule-id="${rule.id}">
        ${optionsHtml(FIELD_OPTS, rule.field)}
      </select>
      <select class="form-select form-select-sm" style="width:auto"
        data-action="update-rule-match" data-rule-id="${rule.id}">
        ${optionsHtml(MATCH_OPTS, rule.match)}
      </select>
      <input
        type="text"
        class="form-control form-control-sm"
        style="min-width:120px;flex:1"
        value="${escapeAttr(rule.value)}"
        data-action="update-rule-value"
        data-rule-id="${rule.id}"
        placeholder="value..."
      />
      <button class="btn btn-sm btn-outline-secondary p-1 lh-1" type="button"
        data-action="move-up"
        data-item-id="${rule.id}"
        data-parent-id="${parentId}"${upDisabled}
        title="Move up">
        <i class="ri-arrow-up-s-line"></i>
      </button>
      <button class="btn btn-sm btn-outline-secondary p-1 lh-1" type="button"
        data-action="move-down"
        data-item-id="${rule.id}"
        data-parent-id="${parentId}"${downDisabled}
        title="Move down">
        <i class="ri-arrow-down-s-line"></i>
      </button>
      <button class="btn btn-sm btn-outline-danger p-1 lh-1" type="button"
        data-action="delete-rule"
        data-item-id="${rule.id}"
        data-parent-id="${parentId}"
        title="Delete rule">
        <i class="ri-close-line"></i>
      </button>
    </div>`
}

function renderFilterGroup(
  group: FilterGroup,
  depth: number,
  isRoot: boolean
): string {
  const opClass = group.operator === 'and' ? 'btn-primary' : 'btn-warning'
  const opLabel = group.operator === 'and' ? 'AND' : 'OR'

  const childrenHtml = group.children
    .map((child, idx) => {
      if (child.type === 'rule') {
        return renderRule(
          child as FilterRule,
          idx,
          group.children.length,
          group.id
        )
      }
      return renderFilterGroup(child as FilterGroup, depth + 1, false)
    })
    .join('')

  const deleteBtn = isRoot
    ? ''
    : `
      <button class="btn btn-sm btn-outline-danger p-1 lh-1" type="button"
        data-action="delete-group"
        data-item-id="${group.id}"
        title="Delete group">
        <i class="ri-delete-bin-line"></i>
      </button>`

  return `
    <div class="filter-group" data-operator="${group.operator}" data-group-id="${group.id}">
      <div class="d-flex align-items-center gap-2 mb-2">
        <button class="btn btn-sm ${opClass}" type="button"
          data-action="toggle-operator"
          data-item-id="${group.id}">
          ${opLabel}
        </button>${deleteBtn}
      </div>
      ${childrenHtml}
      <div class="d-flex gap-2 mt-1">
        <button class="btn btn-sm btn-outline-secondary" type="button"
          data-action="add-rule"
          data-item-id="${group.id}">
          <i class="ri-add-line me-1"></i>Add Rule
        </button>
        <button class="btn btn-sm btn-outline-secondary" type="button"
          data-action="add-group"
          data-item-id="${group.id}">
          <i class="ri-add-line me-1"></i>Add Inner Group
        </button>
      </div>
    </div>`
}

function render(): void {
  if (!_root || !_config) return
  const { mode, match_whole_word, root } = _config
  _root.innerHTML = `
    <div class="mb-3 d-flex align-items-center flex-wrap gap-3">
      <div class="d-flex align-items-center gap-2">
        <span class="text-muted small">Mode:</span>
        <div class="form-check mb-0">
          <input class="form-check-input" type="radio" name="filter-mode" id="filter-mode-bl"
            value="blacklist" data-action="set-mode"${mode === 'blacklist' ? ' checked' : ''} />
          <label class="form-check-label" for="filter-mode-bl">Blacklist</label>
        </div>
        <div class="form-check mb-0">
          <input class="form-check-input" type="radio" name="filter-mode" id="filter-mode-wl"
            value="whitelist" data-action="set-mode"${mode === 'whitelist' ? ' checked' : ''} />
          <label class="form-check-label" for="filter-mode-wl">Whitelist</label>
        </div>
      </div>
      <div class="form-check mb-0">
        <input class="form-check-input" type="checkbox" id="filter-whole-word"
          data-action="toggle-whole-word"${match_whole_word ? ' checked' : ''} />
        <label class="form-check-label" for="filter-whole-word">Whole words only</label>
      </div>
    </div>
    ${renderFilterGroup(root, 0, true)}`
}

// ---------------------------------------------------------------------------
// Event handlers (delegated from root)
// ---------------------------------------------------------------------------
function handleClick(e: Event): void {
  const target = e.target as HTMLElement
  const btn = target.closest('button[data-action]') as HTMLButtonElement | null
  if (!btn || !_config) return

  const action = btn.dataset.action as string
  const itemId = btn.dataset.itemId
  const parentId = btn.dataset.parentId

  switch (action) {
    case 'add-rule': {
      if (!itemId) break
      const grp = findGroup(_config.root, itemId)
      if (grp) {
        grp.children.push(mkRule())
        render()
      }
      break
    }
    case 'add-group': {
      if (!itemId) break
      const grp = findGroup(_config.root, itemId)
      if (grp) {
        grp.children.push(mkGroup())
        render()
      }
      break
    }
    case 'delete-rule': {
      if (!itemId || !parentId) break
      const grp = findGroup(_config.root, parentId)
      if (grp) {
        grp.children = grp.children.filter((c) => c.id !== itemId)
        render()
      }
      break
    }
    case 'delete-group': {
      if (!itemId) break
      const parent = findParentOf(_config.root, itemId)
      if (parent) {
        parent.children = parent.children.filter((c) => c.id !== itemId)
        render()
      }
      break
    }
    case 'move-up': {
      if (!itemId || !parentId) break
      moveItem(parentId, itemId, -1)
      break
    }
    case 'move-down': {
      if (!itemId || !parentId) break
      moveItem(parentId, itemId, 1)
      break
    }
    case 'toggle-operator': {
      if (!itemId) break
      const grp = findGroup(_config.root, itemId)
      if (grp) {
        grp.operator = grp.operator === 'and' ? 'or' : 'and'
        render()
      }
      break
    }
  }
}

function handleChange(e: Event): void {
  const target = e.target as HTMLInputElement | HTMLSelectElement
  const action = target.dataset.action
  if (!_config || !action) return

  switch (action) {
    case 'set-mode':
      _config.mode = (target as HTMLInputElement).value as FilterConfig['mode']
      break
    case 'toggle-whole-word':
      _config.match_whole_word = (target as HTMLInputElement).checked
      break
    case 'update-rule-field': {
      const rule = findRule(_config.root, target.dataset.ruleId ?? '')
      if (rule) rule.field = target.value as FilterRule['field']
      break
    }
    case 'update-rule-match': {
      const rule = findRule(_config.root, target.dataset.ruleId ?? '')
      if (rule) rule.match = target.value as FilterRule['match']
      break
    }
    case 'update-rule-value': {
      const rule = findRule(_config.root, target.dataset.ruleId ?? '')
      if (rule) rule.value = target.value
      break
    }
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Initialize the filter builder in the given root element.
 * Binds event listeners (idempotent — safe to call multiple times on the same element).
 */
export function initFilterBuilder(
  root: HTMLElement,
  initial: FilterConfig | null
): void {
  _root = root
  _config = initial ? (JSON.parse(JSON.stringify(initial)) as FilterConfig) : null
  if (_config) render()

  // Bind once per DOM element using a data attribute flag
  if (!root.dataset.filterBound) {
    root.dataset.filterBound = 'true'
    root.addEventListener('click', handleClick)
    // 'change' handles selects / radios / checkboxes; 'input' handles text fields live
    root.addEventListener('change', handleChange)
    root.addEventListener('input', handleChange)
  }
}

/**
 * Returns a deep copy of the current FilterConfig, or null if none is set.
 */
export function getFilterConfig(): FilterConfig | null {
  return _config ? (JSON.parse(JSON.stringify(_config)) as FilterConfig) : null
}

/**
 * Replace the current config and re-render.
 * Pass null to clear the config.
 */
export function setFilterConfig(config: FilterConfig | null): void {
  _config = config ? (JSON.parse(JSON.stringify(config)) as FilterConfig) : null
  if (_root) render()
}
