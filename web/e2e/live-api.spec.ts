import { expect, test } from '@playwright/test'

test('live API persists a draft, evidence metadata, and audit history across reloads', async ({ page }) => {
  const title = 'Browser persistence integration case'
  const evidenceTitle = 'E2E fire safety certificate'

  await page.goto('/')
  await page.getByLabel('Email address').fill('demo.institution@example.test')
  await page.getByLabel('Password').fill('PRAVAAH-E2E-Only-Password-2026!')
  await page.getByRole('button', { name: 'Sign in' }).click()

  await expect(page.getByRole('heading', { name: 'Good to see you, Demo.' })).toBeVisible()
  await page.getByRole('button', { name: 'New application' }).click()
  await expect(page.getByRole('heading', { name: 'Create a draft application' })).toBeVisible()
  await page.getByLabel('Application title').fill(title)
  await page.getByLabel('Short description').fill('Created through the browser against the real FastAPI and SQLite test database.')
  await page.getByRole('button', { name: 'Create draft' }).click()
  await expect(page.getByText('Draft application created successfully.')).toBeVisible()

  // Reload proves the new draft was committed to the real API database, not held in mock state.
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Good to see you, Demo.' })).toBeVisible()
  await expect(page.getByText(title).first()).toBeVisible()
  await page.getByText(title).first().click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()

  await page.getByLabel('Evidence title').fill(evidenceTitle)
  await page.getByRole('button', { name: 'Register evidence' }).click()
  await expect(page.getByText(evidenceTitle).first()).toBeVisible()
  await expect(page.getByText('Audit chain verified')).toBeVisible()

  // A second reload verifies the evidence row and its audit event were persisted.
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Good to see you, Demo.' })).toBeVisible()
  await page.getByText(title).first().click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()
  await expect(page.getByText(evidenceTitle).first()).toBeVisible()
  await expect(page.getByText('Audit chain verified')).toBeVisible()
  await expect(page.getByText(/\d+ events checked\. No tampering detected in the stored chain\./)).toBeVisible()
  await expect(page.getByText('evidence registered', { exact: false }).first()).toBeVisible()
})
