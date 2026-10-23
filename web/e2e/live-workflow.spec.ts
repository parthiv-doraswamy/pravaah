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

  const institutionRegistry = await request.get('http://127.0.0.1:8000/api/v1/applications?page=1&page_size=100', {
    headers: institutionHeaders,
  })
  expect(institutionRegistry.status()).toBe(200)
  const institutionCases = await institutionRegistry.json() as {
    items: { id: string; application_number: string; status: string }[]
  }
  const draft = institutionCases.items.find(item => item.application_number === 'PVH-DEMO-1001')
  const submitted = institutionCases.items.find(item => item.application_number === 'PVH-DEMO-1002')
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

  // The reviewer can see the registry, but the institution cannot see the other institution's case.
  const reviewerRegistry = await request.get('http://127.0.0.1:8000/api/v1/applications?page=1&page_size=100', {
    headers: reviewerHeaders,
  })
  expect(reviewerRegistry.status()).toBe(200)
  const reviewerCases = await reviewerRegistry.json() as {
    items: { id: string; application_number: string; status: string }[]
  }
  const foreign = reviewerCases.items.find(item => item.application_number === 'PVH-DEMO-2001')
  expect(foreign, 'second synthetic institution case must exist').toBeTruthy()

  const foreignDetail = await request.get(
    `http://127.0.0.1:8000/api/v1/applications/${foreign!.id}`,
    { headers: institutionHeaders },
  )
  expect(foreignDetail.status()).toBe(404)
  const foreignTimeline = await request.get(
    `http://127.0.0.1:8000/api/v1/applications/${foreign!.id}/events`,
    { headers: institutionHeaders },
  )
  expect(foreignTimeline.status()).toBe(404)

  // A valid reviewer action updates status and creates a verifiable audit event.
  const transition = await request.post(
    `http://127.0.0.1:8000/api/v1/applications/${submitted!.id}/transitions`,
    {
      headers: reviewerHeaders,
      data: {
        expected_status: 'submitted',
        target_status: 'under_scrutiny',
        reason: 'Live API browser integration test',
      },
    },
  )
  expect(transition.status(), await transition.text()).toBe(200)
  expect((await transition.json()).status).toBe('under_scrutiny')

  const verification = await request.get(
    `http://127.0.0.1:8000/api/v1/applications/${submitted!.id}/events/verify`,
    { headers: reviewerHeaders },
  )
  expect(verification.status()).toBe(200)
  const chain = await verification.json() as { valid: boolean; event_count: number; first_invalid_sequence: number | null }
  expect(chain.valid).toBe(true)
  expect(chain.event_count).toBeGreaterThanOrEqual(2)
  expect(chain.first_invalid_sequence).toBeNull()

  const timeline = await request.get(
    `http://127.0.0.1:8000/api/v1/applications/${submitted!.id}/events`,
    { headers: reviewerHeaders },
  )
  expect(timeline.status()).toBe(200)
  const events = await timeline.json() as { sequence: number; event_type: string; to_status: string | null }[]
  expect(events.map(event => event.sequence)).toEqual(events.map((_, index) => index + 1))
  expect(events.some(event => event.to_status === 'under_scrutiny')).toBe(true)
})
