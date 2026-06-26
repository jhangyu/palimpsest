/*
---
name: smoke
description: "Stage 1 smoke tests — homepage HTTP 200 and no console errors"
stage: stage1
type: playwright
target:
  layer: frontend
  domain: smoke
spec_doc: null
test_file: tests/stage2/e2e/stage1/smoke.spec.ts
tests:
  - name: "homepage loads"
    line: 3
    purpose: "Verify homepage returns HTTP 200 status"
  - name: "no console errors"
    line: 8
    purpose: "Verify no JavaScript console errors on homepage load"
run:
  command: "cd frontend-astro && npx playwright test tests/stage2/e2e/stage1/smoke.spec.ts"
  prerequisites:
    - "App running on http://localhost:5174"
---
*/
import { test, expect } from '@playwright/test'

test('homepage loads', async ({ page }) => {
  const response = await page.goto('/')
  expect(response?.status()).toBe(200)
})

test('no console errors', async ({ page }) => {
  const errors: string[] = []
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text())
  })
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  expect(errors).toHaveLength(0)
})
