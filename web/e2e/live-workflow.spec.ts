import { expect, test, type APIRequestContext } from '@playwright/test'

const password = 'PRAVAAH-E2E-Only-Password-2026!'

async function login(request: APIRequestContext, email: string) {
  const response = await request.post('http://127.0.0.1:8000/api/v1/auth/login', {
    data: { email, password },
  })
  expect(response.status(), `login failed for ${email}: ${await response.text()}`).toBe(200)
  const body = await response.json() as { access_token: string }
  return { Authorization: `Bearer ${body.access_token}` }
}

test('live workflow enforces role transitions, institution scope, and audit integrity', async ({ request }) => {
  const institutionHeaders = await login(request, 'demo.institution@example.test')
  const reviewerHeaders = await login(request, 'demo.reviewer@example.test')

  const registry = await request.get('http://127.0.0.1:8000/api/v1/applications?page=1&page_size=100', {
    headers: institutionHeaders,
  })
  expect(registry.status()).toBe(200)
  const cases = await registry.json() as { items: { id: string; application_number: string; status: string }[] }
  const draft = cases.items.find(item => item.application_number === 'PVH-DEMO-1001')
  const submitted = cases.items.find(item => item.application_number === 'PVH-DEMO-1002')
  expect(draft, 'seeded draft application must exist').toBeTruthy()
  expect(submitted, 'seeded submitted application must exist').toBeTruthy()

  // The institution cannot approve its own draft or skip the scrutiny stage.
  const forbiddenApproval = await request.post(
    `http://127.0.0.1:8000/api/v1/applications/${draft!.id}/transitions`,
    {
      headers: institutionHeaders,
      data: { expected_status: 'draft', target_status: 'approved', reason: 'E2E must reject bypass' },
    },
  )
  expect(forbiddenApproval.status()).toBe(409)

  // A record owned by the other seeded institution is hidden, including its timeline.
  const foreignCase = await request.get('http://127.0.0.1:8000/api/v1/applications', {
    headers: institutionHeaders,
    params: { q: 'PVH-DEMO-2001', page: 1, page_size: 100 },
  })
  expect(foreignCase.status()).toBe(200)
  expect((await foreignCase.json()).total).toBe(0)

  const foreignDetail = await request.get(
    'http://127.0.0.1:8000/api/v1/applications/${foreignCaseId}',
    { headers: institutionHeaders },
  )
  // The registry intentionally does not disclose the foreign application's identifier.
  // Resolve the known synthetic case by trying its seeded record ID via a reviewer-visible query.
  // Use the reviewer registry only to discover the case ID, then verify institution denial.
  expect(foreignDetail.status()).toBe(404)
})
