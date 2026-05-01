import { test, expect } from '@playwright/test';

test.describe('Astro Frontend E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('Dashboard page loads without errors', async ({ page }) => {
    // Check page loads
    await expect(page).toHaveTitle(/palimpsest/);

    // Check sidebar is visible
    const sidebar = page.locator('.sidebar');
    await expect(sidebar).toBeVisible();

    // Check logo text
    await expect(page.locator('.logo-container')).toContainText('palimpsest');

    // Check navigation links
    await expect(page.locator('.nav-item').first()).toBeVisible();
  });

  test('Sidebar navigation works', async ({ page }) => {
    // Click Create Feed link
    await page.click('a[href="/add"]');

    // Should navigate to add page
    await expect(page).toHaveURL(/\/add/);

    // Check wizard form is visible
    await expect(page.locator('.wizard-container')).toBeVisible();
  });

  test('Dashboard shows metrics cards', async ({ page }) => {
    // Check for metric cards
    const metricCards = page.locator('.metric-card');
    await expect(metricCards).toHaveCount(3);

    // Check for specific metrics
    await expect(page.locator('text=Total Feeds')).toBeVisible();
    await expect(page.locator('text=System Status')).toBeVisible();
    await expect(page.locator('text=Active Services')).toBeVisible();
  });

  test('No console errors on page load', async ({ page }) => {
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Filter out known non-critical errors
    const criticalErrors = errors.filter(err =>
      !err.includes('favicon') &&
      !err.includes('net::ERR_')
    );

    expect(criticalErrors).toHaveLength(0);
  });
});

test.describe('Create Feed Page', () => {
  test('Create Feed wizard renders correctly', async ({ page }) => {
    await page.goto('/add');

    // Check form elements
    await expect(page.locator('text=Create New Feed')).toBeVisible();
    await expect(page.locator('input[placeholder*="example.com"]')).toBeVisible();

    // Check action buttons
    await expect(page.locator('button:has-text("Analyze List")')).toBeVisible();
    await expect(page.locator('button:has-text("Analyze Content")')).toBeVisible();
    await expect(page.locator('button:has-text("Start Crawling")')).toBeVisible();
  });
});

test.describe('Edit Feed Page', () => {
  test('Edit Feed page renders correctly', async ({ page }) => {
    await page.goto('/edit');

    // Check page title
    await expect(page.locator('text=Feed Management')).toBeVisible();
  });
});
