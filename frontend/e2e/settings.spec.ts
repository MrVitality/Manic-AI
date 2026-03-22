import { test, expect } from '@playwright/test'

test.describe('Settings', () => {
  test('can change theme', async ({ page }) => {
    await page.goto('/settings')
    // Find and click theme toggle
  })

  test('can change model', async ({ page }) => {
    await page.goto('/settings')
    // Navigate to inference settings
  })

  test('settings persist across navigation', async ({ page }) => {
    await page.goto('/settings')
    // Change a setting, navigate away, come back, verify it persists
  })
})
