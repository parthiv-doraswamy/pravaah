export type User = {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  institution_id: string | null
}

export type Application = {
  id: string
  application_number: string
  title: string
  status: string
  summary: string | null
  institution_id: string
  submitted_at: string | null
  created_at: string
  updated_at: string
}

export type ApplicationPage = {
  items: Application[]
  page: number
  page_size: number
  total: number
}

export type TokenResponse = {
  access_token: string
  token_type: string
  expires_in: number
}

export type ApplicationEvent = {
  id: string
  application_id: string
  sequence: number
  event_type: string
  from_status: string | null
  to_status: string | null
  actor_user_id: string | null
  reason: string | null
  event_metadata: Record<string, unknown>
  occurred_at: string
  previous_hash: string
  event_hash: string
}

export type EventVerification = {
  application_id: string
  valid: boolean
  event_count: number
  first_invalid_sequence: number | null
}

export type ApplicationEvidence = {
  id: string
  application_id: string
  title: string
  category: string
  reference_number: string | null
  issued_on: string | null
  expires_on: string | null
  policy_key: string | null
  notes: string | null
  created_by_user_id: string | null
  created_at: string
  updated_at: string
}

export type EvidenceAttachment = {
  id: string
  application_id: string
  evidence_id: string
  original_filename: string
  content_type: string
  size_bytes: number
  sha256_hex: string
  uploaded_by_user_id: string | null
  created_at: string
}

export type ComplianceSubmission = {
  id: string
  application_id: string
  submission_type: string
  title: string
  declaration: string
  evidence_ids: string[]
  status: 'submitted' | 'accepted' | 'changes_requested' | 'rejected'
  version: number
  submitted_by_user_id: string | null
  submitted_at: string | null
  reviewed_by_user_id: string | null
  reviewed_at: string | null
  review_notes: string | null
  supersedes_submission_id: string | null
  created_at: string
  updated_at: string
}

export type EvidenceCreate = {
  title: string
  category: string
  reference_number?: string
  issued_on?: string
  expires_on?: string
  policy_key?: string
  notes?: string
}

export type PolicyVersion = {
  id: string
  policy_key: string
  version: number
  title: string
  description: string
  effective_from: string
  rules: Record<string, unknown>
  source_label: string
  is_active: boolean
  created_at: string
}


export type EvidenceAlert = {
  evidence_id: string
  application_id: string
  application_number: string
  application_title: string
  title: string
  category: string
  policy_key: string | null
  expires_on: string
  days_remaining: number
  severity: 'expired' | 'urgent' | 'warning' | 'upcoming'
}

export type ComplianceEscalation = {
  id: string
  application_id: string
  evidence_id: string
  escalation_type: string
  status: string
  severity: string
  summary: string
  triggered_at: string
  resolved_at: string | null
}

export type ComplianceOverview = {
  as_of: string
  total_evidence: number
  expired: number
  due_within_1_day: number
  due_within_7_days: number
  due_within_30_days: number
  without_expiry: number
  alerts: EvidenceAlert[]
  warning_windows_days: number[]
  warning_source: string
}


export type NotificationRecord = {
  id: string
  application_id: string
  evidence_id: string | null
  notification_type: string
  title: string
  message: string
  severity: string
  delivery_status: string
  attempt_count: number
  max_attempts: number
  next_attempt_at: string | null
  last_error: string | null
  created_at: string
  read_at: string | null
  sent_at: string | null
}

export type NotificationQueueResult = {
  as_of: string
  created: number
  skipped_existing: number
  recipient_count: number
  detail: string
}

export type EVCVisit = {
  id: string
  application_id: string
  scheduled_for: string
  mode: 'onsite' | 'virtual'
  location: string | null
  notes: string | null
  status: 'scheduled' | 'completed' | 'cancelled'
  checklist: { key: string; label: string; result: 'pass' | 'needs_attention' | 'not_applicable'; notes: string | null }[] | null
  linked_evidence_ids: string[] | null
  outcome_summary: string | null
  observations: string | null
  report_status: 'not_started' | 'draft' | 'submitted'
  report_submitted_at: string | null
  created_by_user_id: string | null
  created_at: string
  updated_at: string
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '')
const TOKEN_KEY = 'pravaah_access_token'

export const getToken = () => sessionStorage.getItem(TOKEN_KEY)
export const saveToken = (token: string) => sessionStorage.setItem(TOKEN_KEY, token)
export const clearToken = () => sessionStorage.removeItem(TOKEN_KEY)

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const payload = await response.json()
      message = typeof payload.detail === 'string' ? payload.detail : message
    } catch {
      // Keep the HTTP status message if the response isn't JSON.
    }
    if (response.status === 401) {
      clearToken()
      window.dispatchEvent(new Event('pravaah:unauthorized'))
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export const api = {
  login: (email: string, password: string) => request<TokenResponse>('/auth/login', {
    method: 'POST', body: JSON.stringify({ email, password }),
  }),
  me: () => request<User>('/auth/me'),
  applications: (options: { page?: number; pageSize?: number; q?: string; status?: string } = {}) => {
    const params = new URLSearchParams()
    params.set('page', String(options.page ?? 1))
    params.set('page_size', String(options.pageSize ?? 50))
    if (options.q) params.set('q', options.q)
    if (options.status) params.set('status', options.status)
    return request<ApplicationPage>(`/applications?${params.toString()}`)
  },
  application: (id: string) => request<Application>(`/applications/${encodeURIComponent(id)}`),
  createApplication: (title: string, summary?: string) => request<Application>('/applications', {
    method: 'POST', body: JSON.stringify({ title, summary: summary || null }),
  }),
  applicationEvents: (id: string) => request<ApplicationEvent[]>(`/applications/${encodeURIComponent(id)}/events`),
  verifyEvents: (id: string) => request<EventVerification>(`/applications/${encodeURIComponent(id)}/events/verify`),
  policies: () => request<PolicyVersion[]>('/applications/policies/registry'),
  complianceOverview: () => request<ComplianceOverview>('/compliance/overview'),
  submissions: (applicationId: string) => request<ComplianceSubmission[]>(`/compliance/applications/${encodeURIComponent(applicationId)}/submissions`),
  createSubmission: (applicationId: string, payload: { submission_type: string; title: string; declaration: string; evidence_ids: string[] }) =>
    request<ComplianceSubmission>(`/compliance/applications/${encodeURIComponent(applicationId)}/submissions`, { method: 'POST', body: JSON.stringify(payload) }),
  reviewSubmission: (id: string, decision: 'accepted' | 'changes_requested' | 'rejected', notes?: string) =>
    request<ComplianceSubmission>(`/compliance/submissions/${encodeURIComponent(id)}/review`, { method: 'POST', body: JSON.stringify({ decision, notes: notes || null }) }),
  resubmitSubmission: (id: string, payload: { submission_type: string; title: string; declaration: string; evidence_ids: string[] }) =>
    request<ComplianceSubmission>(`/compliance/submissions/${encodeURIComponent(id)}/resubmit`, { method: 'POST', body: JSON.stringify(payload) }),
  escalations: (openOnly = true) => request<ComplianceEscalation[]>(`/compliance/escalations?open_only=${openOnly}`),
  resolveEscalation: (id: string) => request<ComplianceEscalation>(`/compliance/escalations/${encodeURIComponent(id)}/resolve`, { method: 'POST' }),
  notifications: (unreadOnly = false) => request<NotificationRecord[]>(`/notifications?unread_only=${unreadOnly}&limit=50`),
  markNotificationRead: (id: string) => request<NotificationRecord>(`/notifications/${encodeURIComponent(id)}/read`, { method: 'POST' }),
  queueExpiryNotifications: () => request<NotificationQueueResult>('/notifications/queue-expiry', { method: 'POST' }),
  evidence: (applicationId: string) => request<ApplicationEvidence[]>(`/applications/${encodeURIComponent(applicationId)}/evidence`),
  registerEvidence: (applicationId: string, payload: EvidenceCreate) => request<ApplicationEvidence>(`/applications/${encodeURIComponent(applicationId)}/evidence`, { method: 'POST', body: JSON.stringify(payload) }),
  evidenceAttachments: (applicationId: string, evidenceId: string) =>
    request<EvidenceAttachment[]>(`/applications/${encodeURIComponent(applicationId)}/evidence/${encodeURIComponent(evidenceId)}/attachments`),
  uploadEvidenceAttachment: async (applicationId: string, evidenceId: string, file: File): Promise<EvidenceAttachment> => {
    const token = getToken()
    const form = new FormData()
    form.append('file', file)
    const response = await fetch(`${API_BASE}/applications/${encodeURIComponent(applicationId)}/evidence/${encodeURIComponent(evidenceId)}/attachments`, {
      method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form,
    })
    if (!response.ok) {
      let message = `Upload failed (${response.status})`
      try { const payload = await response.json(); if (typeof payload.detail === 'string') message = payload.detail } catch { /* Keep HTTP status. */ }
      throw new Error(message)
    }
    return response.json() as Promise<EvidenceAttachment>
  },
  downloadEvidenceAttachment: async (applicationId: string, evidenceId: string, attachmentId: string): Promise<Blob> => {
    const token = getToken()
    const response = await fetch(`${API_BASE}/applications/${encodeURIComponent(applicationId)}/evidence/${encodeURIComponent(evidenceId)}/attachments/${encodeURIComponent(attachmentId)}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) throw new Error(`Download failed (${response.status})`)
    return response.blob()
  },
  evcVisits: (options: { status?: string; applicationId?: string } = {}) => {
    const params = new URLSearchParams()
    if (options.status) params.set('status_filter', options.status)
    if (options.applicationId) params.set('application_id', options.applicationId)
    return request<EVCVisit[]>(`/evc/visits${params.size ? `?${params.toString()}` : ''}`)
  },
  scheduleEVCVisit: (payload: { application_id: string; scheduled_for: string; mode: 'onsite' | 'virtual'; location?: string; notes?: string }) =>
    request<EVCVisit>('/evc/visits', { method: 'POST', body: JSON.stringify(payload) }),
  updateEVCVisitStatus: (id: string, status: 'completed' | 'cancelled') =>
    request<EVCVisit>(`/evc/visits/${encodeURIComponent(id)}/status`, { method: 'POST', body: JSON.stringify({ status }) }),
  saveEVCReport: (id: string, payload: { checklist: { key: string; label: string; result: 'pass' | 'needs_attention' | 'not_applicable'; notes?: string | null }[]; outcome_summary: string; observations?: string; evidence_ids: string[]; submit: boolean }) =>
    request<EVCVisit>(`/evc/visits/${encodeURIComponent(id)}/report`, { method: 'PUT', body: JSON.stringify(payload) }),
  transitionApplication: (id: string, targetStatus: string, expectedStatus: string, reason?: string) =>
    request<Application>(`/applications/${encodeURIComponent(id)}/transitions`, {
      method: 'POST',
      body: JSON.stringify({ target_status: targetStatus, expected_status: expectedStatus, reason: reason || null }),
    }),
}
