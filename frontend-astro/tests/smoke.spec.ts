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
