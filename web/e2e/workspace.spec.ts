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

    if (path === '/operations/reports/applications/export') {
      await route.fulfill({ status: 200, contentType: 'text/csv; charset=utf-8', body: '\uFEFFapplication_number,title,status\\nPVH-E2E-0001,Existing demo application,draft\\n' })
      return
    }

    if (path === '/operations/metrics') {
      await route.fulfill({ json: {
        as_of: '2026-10-23', total_applications: applications.length, active_applications: applications.length,
        awaiting_review: 0, completed_applications: 0, applications_by_status: { draft: applications.length },
        submissions_pending_review: 0, expired_evidence: 0, evidence_due_within_7_days: 0,
        open_escalations: 0, failed_notifications: 0, evc_reports_pending: 0,
      } })
      return
    }

    if (path === '/operations/pendency') {
      await route.fulfill({ json: {
        as_of: '2026-10-23', total_pending: 0,
        aging_buckets: { '0-2_days': 0, '3-7_days': 0, '8-14_days': 0, '15+_days': 0 },
        by_status: [], oldest_items: [],
      } })
      return
    }

    if (path === '/operations/inbox') {
      await route.fulfill({ json: {
        as_of: '2026-10-23', total: 1, by_priority: { high: 0, medium: 0, low: 1 },
        by_type: { application_workflow: 1 }, items: [{
          task_id: 'application:30000000-0000-4000-8000-000000000001', task_type: 'application_workflow',
          title: 'Complete draft application', description: 'Finish the draft and submit it for scrutiny',
          priority: 'low', status: 'draft', application_id: initialApplication.id,
          application_number: initialApplication.application_number, application_title: initialApplication.title,
          institution_name: 'Demo Institution', created_at: '2026-10-20', due_date: null, action_view: 'detail',
        }],
      } })
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
  await expect(page.getByText('Existing demo application').first()).toBeVisible()

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

  await page.getByRole('button', { name: 'Task inbox' }).click()
  await expect(page.getByRole('heading', { name: 'Prioritized task list' })).toBeVisible()
  await expect(page.getByText('Complete draft application')).toBeVisible()

  await page.getByRole('button', { name: 'Reports & exports' }).click()
  await expect(page.getByRole('heading', { name: 'Operational reports' })).toBeVisible()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export CSV' }).first().click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('pravaah-applications-report.csv')
})


test('institution can register evidence and verify the application audit timeline', async ({ page }) => {
  const application = { ...initialApplication }
  const evidence: Record<string, unknown>[] = []
  const events: Record<string, unknown>[] = []

  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/api/v1', '')
    const appId = application.id

    if (path === '/auth/login' && request.method() === 'POST') {
      await route.fulfill({ json: { access_token: 'e2e-access-token', token_type: 'bearer', expires_in: 3600 } })
      return
    }
    if (path === '/auth/me') {
      await route.fulfill({ json: institution })
      return
    }
    if (path === '/applications' && request.method() === 'GET') {
      await route.fulfill({ json: { items: [application], page: 1, page_size: 100, total: 1 } })
      return
    }
    if (path === `/applications/${appId}` && request.method() === 'GET') {
      await route.fulfill({ json: application })
      return
    }
    if (path === `/applications/${appId}/evidence` && request.method() === 'GET') {
      await route.fulfill({ json: evidence })
      return
    }
    if (path === `/applications/${appId}/evidence` && request.method() === 'POST') {
      const body = request.postDataJSON() as Record<string, unknown>
      const created = {
        id: '40000000-0000-4000-8000-000000000001',
        application_id: appId,
        title: body.title,
        category: body.category,
        reference_number: body.reference_number ?? null,
        issued_on: body.issued_on ?? null,
        expires_on: body.expires_on ?? null,
        policy_key: body.policy_key ?? null,
        notes: body.notes ?? null,
        created_by_user_id: institution.id,
        created_at: '2026-10-23T10:00:00Z',
        updated_at: '2026-10-23T10:00:00Z',
      }
      evidence.push(created)
      events.push({
        id: '50000000-0000-4000-8000-000000000001',
        application_id: appId,
        sequence: 1,
        event_type: 'evidence_registered',
        from_status: null,
        to_status: null,
        actor_user_id: institution.id,
        reason: 'Evidence metadata registered',
        event_metadata: { evidence_id: created.id },
        occurred_at: '2026-10-23T10:00:00Z',
        previous_hash: 'GENESIS',
        event_hash: 'e2e-audit-hash-001',
      })
      await route.fulfill({ status: 201, json: created })
      return
    }
    if (path === `/applications/${appId}/policy-to-proof`) {
      await route.fulfill({ json: {
        as_of: '2026-10-23T10:00:00Z',
        disclaimer: 'Traceability dossier for human review. Policy records may be synthetic demo assumptions and are not official AICTE rules or a statutory decision.',
        application: {
          id: appId, application_number: application.application_number, title: application.title,
          status: application.status, institution_id: application.institution_id,
          created_at: application.created_at, updated_at: application.updated_at,
        },
        policy_versions: [{
          id: '70000000-0000-4000-8000-000000000001', policy_key: 'EVIDENCE_EXPIRY', version: 1,
          title: 'Evidence expiry demo policy', description: 'Synthetic traceability policy.',
          effective_from: '2026-01-01T00:00:00Z', rules_schema_version: 1,
          source_label: 'Synthetic test policy', is_active: true,
        }],
        policy_evidence_links: [{
          evidence_id: '71000000-0000-4000-8000-000000000001',
          evidence_title: 'Fire safety certificate',
          policy_key: 'EVIDENCE_EXPIRY',
          matched: true,
          policy_versions: [{
            id: '70000000-0000-4000-8000-000000000001',
            version: 1,
            title: 'Evidence expiry demo policy',
            source_label: 'Synthetic test policy',
            is_active: true,
          }],
        }],
        evidence: [], attachments: [], compliance_submissions: [], evc_visits: [], notifications: [], escalations: [],
        audit: { event_count: 0, valid: true, first_invalid_sequence: null, events: [] },
        counts: { policy_versions: 1, evidence: 0, attachments: 0, compliance_submissions: 0, evc_visits: 0, notifications: 0, escalations: 0 },
      } })
      return
    }
    if (path === `/applications/${appId}/events`) {
      await route.fulfill({ json: events })
      return
    }
    if (path === `/applications/${appId}/events/verify`) {
      await route.fulfill({ json: {
        application_id: appId, valid: true, event_count: events.length, first_invalid_sequence: null,
      } })
      return
    }
    if (path.startsWith(`/applications/${appId}/evidence/`) && path.endsWith('/attachments')) {
      await route.fulfill({ json: [] })
      return
    }
    if (path === '/operations/metrics') {
      await route.fulfill({ json: {
        as_of: '2026-10-23', total_applications: 1, active_applications: 1,
        awaiting_review: 0, completed_applications: 0, applications_by_status: { draft: 1 },
        submissions_pending_review: 0, expired_evidence: 0, evidence_due_within_7_days: 0,
        open_escalations: 0, failed_notifications: 0, evc_reports_pending: 0,
      } })
      return
    }

    if (path === '/operations/pendency') {
      await route.fulfill({ json: {
        as_of: '2026-10-23', total_pending: 0,
        aging_buckets: { '0-2_days': 0, '3-7_days': 0, '8-14_days': 0, '15+_days': 0 },
        by_status: [], oldest_items: [],
      } })
      return
    }

    if (path === '/evc/visits' || path === '/compliance/overview' || path === '/compliance/escalations' || path === '/notifications' || path === '/policies') {
      await route.fulfill({ json: path === '/compliance/overview' ? {
        as_of: '2026-10-23', total_evidence: 0, expired: 0, due_within_1_day: 0,
        due_within_7_days: 0, due_within_30_days: 0, without_expiry: 0,
        alerts: [], warning_windows_days: [30, 7, 1], warning_source: 'Synthetic test data.',
      } : [] })
      return
    }
    await route.fulfill({ json: [] })
  })

  await page.goto('/')
  await page.getByLabel('Email address').fill(institution.email)
  await page.getByLabel('Password').fill('correct-demo-password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Good to see you, Demo.' })).toBeVisible()
  await page.getByRole('button', { name: 'Open PVH-E2E-0001' }).click()

  await expect(page.getByRole('heading', { name: 'Existing demo application' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Policy-to-Proof dossier' })).toBeVisible()
  await expect(page.getByText('Evidence expiry demo policy · v1')).toBeVisible()
  await expect(page.getByText('Policy version linked')).toBeVisible()
  await expect(page.getByText('Traceability dossier for human review.', { exact: false })).toBeVisible()
  const dossierDownloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export JSON' }).click()
  const dossierDownload = await dossierDownloadPromise
  expect(dossierDownload.suggestedFilename()).toBe('pravaah-policy-to-proof-PVH-E2E-0001.json')
  const auditDownloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export audit CSV' }).click()
  const auditDownload = await auditDownloadPromise
  expect(auditDownload.suggestedFilename()).toBe('pravaah-audit-PVH-E2E-0001.csv')
  await page.getByLabel('Evidence title').fill('Fire safety certificate')
  await page.getByRole('button', { name: 'Register evidence' }).click()

  await expect(page.getByText('Fire safety certificate').first()).toBeVisible()
  await expect(page.getByText('Audit chain verified').first()).toBeVisible()
  await expect(page.getByText('evidence registered')).toBeVisible()
  await expect(page.getByText('1 events checked. No tampering detected in the stored chain.')).toBeVisible()
  expect(evidence).toHaveLength(1)
  expect(events).toHaveLength(1)
})


test('operations reviewer can inspect failed deliveries and retry within scope', async ({ page }) => {
  const reviewer = {
    ...institution,
    id: '10000000-0000-4000-8000-000000000009',
    email: 'reviewer@example.test',
    full_name: 'Operations Reviewer',
    role: 'scrutiny_officer',
    institution_id: null,
  }
  let retryCalls = 0
  let deliveryStatus = 'failed'
  const notification = {
    id: '60000000-0000-4000-8000-000000000001',
    application_id: initialApplication.id,
    application_number: initialApplication.application_number,
    application_title: initialApplication.title,
    recipient_name: 'Demo Institution',
    recipient_role: 'institution_user',
    notification_type: 'evidence_expiry',
    title: 'Evidence expires soon: Accreditation certificate',
    message: 'Review the evidence record.',
    severity: 'warning',
    delivery_status: deliveryStatus,
    attempt_count: 5,
    max_attempts: 5,
    next_attempt_at: null,
    last_error: 'Provider connection failed; credentials redacted.',
    created_at: '2026-10-22T10:00:00Z',
    updated_at: '2026-10-22T10:00:00Z',
    read_at: null,
    sent_at: null,
    evidence_id: null,
  }

  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/api/v1', '')
    if (path === '/auth/login' && request.method() === 'POST') {
      await route.fulfill({ json: { access_token: 'reviewer-token', token_type: 'bearer', expires_in: 3600 } })
      return
    }
    if (path === '/auth/me') { await route.fulfill({ json: reviewer }); return }
    if (path === '/applications' && request.method() === 'GET') {
      await route.fulfill({ json: { items: [initialApplication], page: 1, page_size: 100, total: 1 } })
      return
    }
    if (path === '/operations/metrics') {
      await route.fulfill({ json: {
        as_of: '2026-10-23', total_applications: 1, active_applications: 1, awaiting_review: 1,
        completed_applications: 0, applications_by_status: { draft: 1 }, submissions_pending_review: 0,
        expired_evidence: 0, evidence_due_within_7_days: 0, open_escalations: 0,
        failed_notifications: 1, evc_reports_pending: 0,
      } })
      return
    }
    if (path === '/operations/pendency') {
      await route.fulfill({ json: { as_of: '2026-10-23', total_pending: 0, aging_buckets: { '0-2_days': 0, '3-7_days': 0, '8-14_days': 0, '15+_days': 0 }, by_status: [], oldest_items: [] } })
      return
    }
    if (path === '/compliance/overview') {
      await route.fulfill({ json: { as_of: '2026-10-23', total_evidence: 0, expired: 0, due_within_1_day: 0, due_within_7_days: 0, due_within_30_days: 0, without_expiry: 0, alerts: [], warning_windows_days: [30, 7, 1], warning_source: 'Fixture' } })
      return
    }
    if (path === '/evc/visits' || path === '/compliance/escalations' || path === '/notifications') {
      await route.fulfill({ json: [] })
      return
    }
    if (path === '/notifications/operations' && request.method() === 'GET') {
      await route.fulfill({ json: {
        as_of: '2026-10-23T10:00:00Z', total: 1,
        by_status: { failed: deliveryStatus === 'failed' ? 1 : 0, pending: deliveryStatus === 'pending' ? 1 : 0 },
        failed: deliveryStatus === 'failed' ? 1 : 0,
        retry_ready: deliveryStatus === 'failed' ? 1 : 0,
        exhausted: 0,
        items: [{ ...notification, delivery_status: deliveryStatus }],
      } })
      return
    }
    if (path === '/notifications/operations/' + notification.id + '/retry' && request.method() === 'POST') {
      retryCalls += 1
      deliveryStatus = 'pending'
      await route.fulfill({ json: { ...notification, delivery_status: 'pending', max_attempts: 6, next_attempt_at: '2026-10-23T10:00:00Z', last_error: null } })
      return
    }
    await route.fulfill({ json: [] })
  })

  await page.goto('/')
  await page.getByLabel('Email address').fill(reviewer.email)
  await page.getByLabel('Password').fill('correct-demo-password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('button', { name: 'Notification ops' }).click()
  await expect(page.getByRole('heading', { name: 'Delivery queue' })).toBeVisible()
  await expect(page.getByText('Provider connection failed; credentials redacted.')).toBeVisible()
  await page.getByRole('button', { name: 'Retry delivery' }).click()
  await expect(page.getByText('Delivery retry queued. Attempt history was preserved and the request was added to the audit trail.')).toBeVisible()
  expect(retryCalls).toBe(1)
})
