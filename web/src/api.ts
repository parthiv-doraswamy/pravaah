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
  createApplication: (title: string, summary?: string) => request<Application>('/applications', {
    method: 'POST', body: JSON.stringify({ title, summary: summary || null }),
  }),
}
