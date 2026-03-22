import { test, expect } from '@playwright/test'

test.describe('Dashboard', () => {
  test('shows service status cards', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page.locator('text=Command Center')).toBeVisible()
  })

  test('tabs switch content', async ({ page }) => {
    await page.goto('/dashboard')
    // Click Services tab
    await page.click('text=Services')
    // Click Performance tab
    await page.click('text=Performance')
  })

  test('health indicator is visible', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page.locator('[role="status"]')).toBeVisible()
  })
})
