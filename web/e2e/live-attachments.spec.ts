import { expect, test, type APIRequestContext } from '@playwright/test'
import { createHash } from 'node:crypto'

const baseURL = 'http://127.0.0.1:8000/api/v1'
const password = 'PRAVAAH-E2E-Only-Password-2026!'

async function login(request: APIRequestContext, email: string) {
  const response = await request.post(`${baseURL}/auth/login`, {
    data: { email, password },
  })
  expect(response.status(), `login failed for ${email}: ${await response.text()}`).toBe(200)
  const body = await response.json() as { access_token: string }
  return { Authorization: `Bearer ${body.access_token}` }
}

test('live API stores, lists, and downloads private evidence attachments with matching hashes', async ({ request }) => {
  const headers = await login(request, 'demo.institution@example.test')
  const registry = await request.get(`${baseURL}/applications?page=1&page_size=100`, { headers })
  expect(registry.status()).toBe(200)
  const registryBody = await registry.json() as {
    items: { id: string; application_number: string }[]
  }
  const application = registryBody.items.find(item => item.application_number === 'PVH-DEMO-1001')
  expect(application, 'seeded draft application must exist').toBeTruthy()

  const evidenceResponse = await request.post(`${baseURL}/applications/${application!.id}/evidence`, {
    headers,
    data: {
      title: 'E2E attachment persistence certificate',
      category: 'safety_certificate',
      reference_number: 'E2E-FILE-001',
      notes: 'Synthetic test record; not an official certificate.',
    },
  })
  expect(evidenceResponse.status(), await evidenceResponse.text()).toBe(201)
  const evidence = await evidenceResponse.json() as { id: string }

  const pdf = Buffer.from('%PDF-1.7\nPRAVAAH synthetic E2E evidence\n%%EOF\n', 'utf8')
  const expectedHash = createHash('sha256').update(pdf).digest('hex')
  const upload = await request.post(
    `${baseURL}/applications/${application!.id}/evidence/${evidence.id}/attachments`,
    {
      headers,
      multipart: {
        file: {
          name: 'synthetic-certificate.pdf',
          mimeType: 'application/pdf',
          buffer: pdf,
        },
      },
    },
  )
  expect(upload.status(), await upload.text()).toBe(201)
  const attachment = await upload.json() as {
    id: string
    original_filename: string
    content_type: string
    size_bytes: number
    sha256_hex: string
  }
  expect(attachment.original_filename).toBe('synthetic-certificate.pdf')
  expect(attachment.content_type).toBe('application/pdf')
  expect(attachment.size_bytes).toBe(pdf.length)
  expect(attachment.sha256_hex).toBe(expectedHash)

  const listed = await request.get(
    `${baseURL}/applications/${application!.id}/evidence/${evidence.id}/attachments`,
    { headers },
  )
  expect(listed.status()).toBe(200)
  expect((await listed.json()).map((item: { id: string }) => item.id)).toContain(attachment.id)

  const downloaded = await request.get(
    `${baseURL}/applications/${application!.id}/evidence/${evidence.id}/attachments/${attachment.id}/download`,
    { headers },
  )
  expect(downloaded.status()).toBe(200)
  expect(Buffer.from(await downloaded.body()).equals(pdf)).toBe(true)
  expect(downloaded.headers()['x-content-type-options']).toBe('nosniff')
  expect(downloaded.headers()['cache-control']).toContain('private')
})

test('live API rejects unsupported attachment extensions and file-signature mismatches', async ({ request }) => {
  const headers = await login(request, 'demo.institution@example.test')
  const registry = await request.get(`${baseURL}/applications?page=1&page_size=100`, { headers })
  expect(registry.status()).toBe(200)
  const registryBody = await registry.json() as {
    items: { id: string; application_number: string }[]
  }
  const application = registryBody.items.find(item => item.application_number === 'PVH-DEMO-1001')
  expect(application, 'seeded draft application must exist').toBeTruthy()

  const evidenceResponse = await request.post(`${baseURL}/applications/${application!.id}/evidence`, {
    headers,
    data: {
      title: 'E2E invalid upload boundary record',
      category: 'other',
      notes: 'Synthetic test record.',
    },
  })
  expect(evidenceResponse.status(), await evidenceResponse.text()).toBe(201)
  const evidence = await evidenceResponse.json() as { id: string }
  const endpoint = `${baseURL}/applications/${application!.id}/evidence/${evidence.id}/attachments`

  const unsupported = await request.post(endpoint, {
    headers,
    multipart: {
      file: {
        name: 'script.html',
        mimeType: 'text/html',
        buffer: Buffer.from('<script>alert(1)</script>', 'utf8'),
      },
    },
  })
  expect(unsupported.status()).toBe(415)

  const mismatched = await request.post(endpoint, {
    headers,
    multipart: {
      file: {
        name: 'not-a-real-pdf.pdf',
        mimeType: 'application/pdf',
        buffer: Buffer.from('plain text, not a PDF', 'utf8'),
      },
    },
  })
  expect(mismatched.status()).toBe(415)

  const listed = await request.get(endpoint, { headers })
  expect(listed.status()).toBe(200)
  expect(await listed.json()).toEqual([])
})
