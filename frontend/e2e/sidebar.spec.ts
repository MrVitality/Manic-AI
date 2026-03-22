import { test, expect } from '@playwright/test'

test.describe('Sidebar', () => {
  test('sidebar is visible on desktop', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('nav')).toBeVisible()
  })

  test('can create new conversation', async ({ page }) => {
    await page.goto('/chat')
    await page.click('text=New Chat')
    // Verify new conversation created
  })

  test('command palette opens with Ctrl+K', async ({ page }) => {
    await page.goto('/')
    await page.keyboard.press('Control+k')
    await expect(page.locator('[role="dialog"]')).toBeVisible()
  })

  test('command palette closes with Escape', async ({ page }) => {
    await page.goto('/')
    await page.keyboard.press('Control+k')
    await expect(page.locator('[role="dialog"]')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator('[role="dialog"]')).not.toBeVisible()
  })
})
