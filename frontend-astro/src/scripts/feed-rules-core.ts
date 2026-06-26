/*
---
name: feed-rules-core
description: "Shared feed editing utilities: JSON parsing, button loading state, source type UI toggling, and CodeMirror initialization — extracted from feed-wizard.ts and feed-edit.ts"
type: script
target:
  layer: frontend
  domain: feed
spec_doc: null
test_file: null
functions:
  - name: parseSafe
    line: 28
    purpose: "Parse a JSON string safely, returning empty object on parse error"
  - name: setLoading
    line: 37
    purpose: "Set a button to loading state and return a restore function to reset it"
  - name: applySourceTypeUi
    line: 72
    purpose: "Apply source type UI state (HTML vs RSS) to toggle disabled sections, relabel buttons, etc."
  - name: initCodeMirror
    line: 129
    purpose: "Initialize a CodeMirror JSON editor on the given element with standard options"
---
*/

// ---------------------------------------------------------------------------
// CodeMirror minimal interface (loaded as global script, not typed package)
// ---------------------------------------------------------------------------
export interface CodeMirrorEditor {
  getValue(): string
  setValue(value: string): void
  refresh(): void
  on(event: string, handler: () => void): void
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/** Parse a JSON string safely, returning empty object on parse error */
export function parseSafe(str: string): Record<string, unknown> {
  try {
    return JSON.parse(str)
  } catch {
    return {}
  }
}

/** Set a button to loading state and return a restore function */
export function setLoading(btn: HTMLButtonElement, html: string): () => void {
  const original = btn.innerHTML
  btn.disabled = true
  btn.innerHTML = html
  return () => {
    btn.innerHTML = original
    btn.disabled = false
  }
}

// ---------------------------------------------------------------------------
// Source Type UI
// ---------------------------------------------------------------------------

export interface SourceTypeElements {
  sourceTypeHtml: HTMLButtonElement | null
  sourceTypeRss: HTMLButtonElement | null
  listRulesSection: HTMLElement | null
  contentRulesSection: HTMLElement | null
  analyzeListBtn: HTMLButtonElement | null
  testListBtn: HTMLButtonElement | null
  testBothBtn: HTMLButtonElement | null
  rssFullContentWrapper: HTMLElement | null
}

export interface SourceTypeState {
  sourceType: 'html' | 'rss'
  rssFullContent: boolean
  rssHasFullContent: boolean
}

/**
 * Apply source type UI state (HTML vs RSS) to toggle disabled sections,
 * relabel buttons, and show/hide full-content options.
 *
 * IMPORTANT: Uses innerHTML (not textContent) for Test List button relabel
 * to preserve Remix Icon elements.
 */
export function applySourceTypeUi(state: SourceTypeState, els: SourceTypeElements): void {
  const isRss = state.sourceType === 'rss'

  // Toggle active class on HTML/RSS buttons
  els.sourceTypeHtml?.classList.toggle('active', !isRss)
  els.sourceTypeRss?.classList.toggle('active', isRss)

  // List rules section (description only, NOT buttons) — disabled in RSS mode
  if (els.listRulesSection) {
    els.listRulesSection.classList.toggle('disabled-section', isRss)
  }

  // Analyze List button — disable individually in RSS mode
  if (els.analyzeListBtn) els.analyzeListBtn.disabled = isRss

  // Test List button — relabel with icons (innerHTML, not textContent)
  if (els.testListBtn) {
    els.testListBtn.innerHTML = isRss
      ? '<i class="ri-rss-line me-1"></i> Parse RSS'
      : '<i class="ri-file-list-line me-1"></i> Test List'
  }

  // Full content option — show only in RSS mode when feed has full content
  if (els.rssFullContentWrapper) {
    els.rssFullContentWrapper.style.display = isRss && state.rssHasFullContent ? '' : 'none'
  }

  // Content rules section — disabled when using RSS full content
  const disableContent = isRss && state.rssFullContent
  if (els.contentRulesSection) {
    els.contentRulesSection.classList.toggle('disabled-section', disableContent)
  }

  // Test Both button
  if (els.testBothBtn) {
    if (isRss && state.rssFullContent) {
      els.testBothBtn.disabled = true
    } else if (isRss) {
      els.testBothBtn.disabled = false
      els.testBothBtn.textContent = 'Parse RSS + Test Content'
    } else {
      els.testBothBtn.disabled = false
      els.testBothBtn.textContent = 'Test Both'
    }
  }
}

// ---------------------------------------------------------------------------
// CodeMirror
// ---------------------------------------------------------------------------

/**
 * Initialize a CodeMirror instance on the given element with JSON mode.
 * Returns the CodeMirror editor instance, or null if the element is not found
 * or window.CodeMirror is not available.
 */
export function initCodeMirror(elementId: string, defaultValue: string): CodeMirrorEditor | null {
  const el = document.getElementById(elementId)
  if (!el) return null

  const CM = (window as unknown as Record<string, unknown>).CodeMirror as
    | ((el: HTMLElement, opts: Record<string, unknown>) => CodeMirrorEditor)
    | undefined
  if (!CM) return null

  return CM(el, {
    value: defaultValue,
    mode: { name: 'javascript', json: true },
    theme: 'default',
    lineNumbers: true,
    lineWrapping: true,
    tabSize: 2,
    indentWithTabs: false,
    matchBrackets: true,
    readOnly: false
  })
}
