import { test, expect } from '@playwright/test'

test.describe('Navigation', () => {
  test('loads the home page', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/Manic AI/)
  })

  test('navigates to chat', async ({ page }) => {
    await page.goto('/chat')
    await expect(page.locator('text=MANIC')).toBeVisible()
  })

  test('navigates to dashboard', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page.locator('text=Command Center')).toBeVisible()
  })

  test('navigates to RAG center', async ({ page }) => {
    await page.goto('/rag')
    await expect(page.locator('text=RAG Center')).toBeVisible()
  })

  test('navigates to documents', async ({ page }) => {
    await page.goto('/documents')
    await expect(page.locator('text=Documents')).toBeVisible()
  })

  test('navigates to settings', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.locator('text=Settings')).toBeVisible()
  })
})
