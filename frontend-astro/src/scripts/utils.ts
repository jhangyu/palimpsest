/*
---
name: utils
description: "Shared HTML and attribute escaping utilities for safe DOM string interpolation"
type: script
target:
  layer: frontend
  domain: utils
spec_doc: null
test_file: null
functions:
  - name: escapeHtml
    line: 16
    purpose: "Escape a string for safe insertion into innerHTML using a temporary div element"
  - name: escapeAttr
    line: 22
    purpose: "Escape special characters in a string for safe use in HTML attribute values"
---
*/
export function escapeHtml(str: string): string {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

export function escapeAttr(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}
