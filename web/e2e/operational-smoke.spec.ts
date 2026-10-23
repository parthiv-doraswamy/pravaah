import { expect, test, type APIRequestContext } from '@playwright/test'

const apiBase = 'http://127.0.0.1:8000'
const apiV1 = `${apiBase}/api/v1`

async function assertHealthy(request: APIRequestContext) {
  const live = await request.get(`${apiBase}/health/live`)
  expect(live.status(), 'liveness endpoint should respond successfully').toBe(200)

  const ready = await request.get(`${apiBase}/health/ready`)
  expect(ready.status(), 'readiness endpoint should confirm database connectivity').toBe(200)
}

test('operational smoke: health checks and synthetic seed baseline are available', async ({ request }) => {
  await assertHealthy(request)

  const login = await request.post(`${apiV1}/auth/login`, {
    data: {
      email: 'demo.institution@example.test',
      password: process.env.PRAVAAH_E2E_PASSWORD,
    },
  })
  expect(login.status(), `synthetic demo login failed: ${await login.text()}`).toBe(200)
  const { access_token: token } = await login.json() as { access_token: string }
  const headers = { Authorization: `Bearer ${token}` }

  const response = await request.get(`${apiV1}/applications?page=1&page_size=100`, { headers })
  expect(response.status(), await response.text()).toBe(200)
  const body = await response.json() as {
    items: { application_number: string }[]
  }

  const visibleNumbers = body.items.map(item => item.application_number)
  expect(visibleNumbers).toContain('PVH-DEMO-1001')
  expect(visibleNumbers).toContain('PVH-DEMO-1002')
  expect(new Set(visibleNumbers).size).toBe(visibleNumbers.length)

  await assertHealthy(request)
})
