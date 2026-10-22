import { expect, test } from '@playwright/test'

const institution = {
  id: '10000000-0000-4000-8000-000000000001',
  email: 'demo.institution@example.test',
  full_name: 'Demo Institution',
  role: 'institution_user',
  is_active: true,
  institution_id: '20000000-0000-4000-8000-000000000001',
}

const initialApplication = {
  id: '30000000-0000-4000-8000-000000000001',
  application_number: 'PVH-E2E-0001',
  title: 'Existing demo application',
  status: 'draft',
  summary: 'Seeded by the browser test.',
  institution_id: institution.institution_id,
  submitted_at: null,
  created_at: '2026-10-20T10:00:00Z',
  updated_at: '2026-10-20T10:00:00Z',
}

test('institution can sign in and create a draft application', async ({ page }) => {
  const applications = [initialApplication]
  let loginAttempts = 0
  let createPayload: Record<string, unknown> | null = null

  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/api/v1', '')

    if (path === '/auth/login' && request.method() === 'POST') {
      loginAttempts += 1
      const body = request.postDataJSON() as { email: string; password: string }
      if (body.password !== 'correct-demo-password') {
        await route.fulfill({ status: 401, json: { detail: 'Invalid email or password' } })
        return
      }
      await route.fulfill({ json: { access_token: 'e2e-access-token', token_type: 'bearer', expires_in: 3600 } })
      return
    }

    if (path === '/auth/me') {
      await route.fulfill({ json: institution })
      return
    }

    if (path === '/applications' && request.method() === 'POST') {
      createPayload = request.postDataJSON() as Record<string, unknown>
      const created = {
        ...initialApplication,
        id: '30000000-0000-4000-8000-000000000002',
        application_number: 'PVH-E2E-0002',
        title: String(createPayload.title),
        summary: createPayload.summary as string | null,
        status: 'draft',
        created_at: '2026-10-23T10:00:00Z',
        updated_at: '2026-10-23T10:00:00Z',
      }
      applications.unshift(created)
      await route.fulfill({ status: 201, json: created })
      return
    }

    if (path === '/applications' && request.method() === 'GET') {
      const q = url.searchParams.get('q')?.toLowerCase() || ''
      const status = url.searchParams.get('status') || ''
      const items = applications.filter(item =>
        item.title.toLowerCase().includes(q) && (!status || item.status === status),
      )
      await route.fulfill({
        json: { items, page: Number(url.searchParams.get('page') || 1), page_size: 100, total: items.length },
      })
      return
    }

    if (path === '/compliance/overview') {
      await route.fulfill({ json: {
        as_of: '2026-10-23', total_evidence: 0, expired: 0, due_within_1_day: 0,
        due_within_7_days: 0, due_within_30_days: 0, without_expiry: 0,
        alerts: [], warning_windows_days: [30, 7, 1], warning_source: 'Synthetic test data.',
      } })
      return
    }

    if (path === '/evc/visits' || path === '/compliance/escalations' || path === '/notifications' || path === '/policies') {
      await route.fulfill({ json: [] })
      return
    }

    if (path.endsWith('/events/verify')) {
      await route.fulfill({ json: {
        application_id: path.split('/')[2], valid: true, event_count: 0, first_invalid_sequence: null,
      } })
      return
    }

    if (/^\/applications\/[^/]+\/events$/.test(path)) {
      await route.fulfill({ json: [] })
      return
    }

    await route.fulfill({ json: [] })
  })

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Sign in to your workspace' })).toBeVisible()

  await page.getByLabel('Email address').fill(institution.email)
  await page.getByLabel('Password').fill('wrong-password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toHaveText('Invalid email or password')

  await page.getByLabel('Password').fill('correct-demo-password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Good to see you, Demo.' })).toBeVisible()
  await expect(page.getByText('Existing demo application')).toBeVisible()

  await page.getByRole('button', { name: 'New application' }).click()
  await expect(page.getByRole('heading', { name: 'Create a draft application' })).toBeVisible()
  await page.getByLabel('Application title').fill('New engineering programme')
  await page.getByLabel('Short description').fill('Browser-tested draft intake.')
  await page.getByRole('button', { name: 'Create draft' }).click()

  await expect(page.getByText('Draft application created successfully.')).toBeVisible()
  await expect(page.getByText('New engineering programme')).toBeVisible()
  expect(loginAttempts).toBe(2)
  expect(createPayload).toMatchObject({
    title: 'New engineering programme',
    summary: 'Browser-tested draft intake.',
  })
})
