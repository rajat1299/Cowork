import { useAuthStore } from '../stores/authStore'

// API base URLs - adjust for your environment
const CORE_API_URL = import.meta.env.VITE_CORE_API_URL || 'http://localhost:3001'
const ORCHESTRATOR_URL = import.meta.env.VITE_ORCHESTRATOR_URL || 'http://localhost:5001'

export { CORE_API_URL, ORCHESTRATOR_URL }

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  headers?: Record<string, string>
  auth?: boolean
}

class ApiError extends Error {
  status: number
  statusText: string
  data?: unknown

  constructor(status: number, statusText: string, data?: unknown) {
    super(`${status} ${statusText}`)
    this.name = 'ApiError'
    this.status = status
    this.statusText = statusText
    this.data = data
  }
}

export { ApiError }

async function refreshAccessToken(): Promise<boolean> {
  const { logout } = useAuthStore.getState()
  try {
    const response = await fetch(`${CORE_API_URL}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })

    if (!response.ok) {
      logout()
      return false
    }

    return true
  } catch {
    logout()
    return false
  }
}

export async function apiRequest<T>(
  baseUrl: string,
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = 'GET', body, headers = {}, auth = true } = options

  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...headers,
  }

  const config: RequestInit = {
    method,
    headers: requestHeaders,
    credentials: 'include',
  }

  if (body && method !== 'GET') {
    config.body = JSON.stringify(body)
  }

  let response = await fetch(`${baseUrl}${endpoint}`, config)

  // Handle 401 - try to refresh token
  if (response.status === 401 && auth) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      response = await fetch(`${baseUrl}${endpoint}`, config)
    }
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new ApiError(response.status, response.statusText, data)
  }

  // Handle empty responses
  const text = await response.text()
  if (!text) return {} as T

  return JSON.parse(text)
}

export async function uploadRequest<T>(
  baseUrl: string,
  endpoint: string,
  formData: FormData,
  auth: boolean = true
): Promise<T> {
  let response = await fetch(`${baseUrl}${endpoint}`, {
    method: 'POST',
    body: formData,
    credentials: 'include',
  })

  if (response.status === 401 && auth) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      response = await fetch(`${baseUrl}${endpoint}`, {
        method: 'POST',
        body: formData,
        credentials: 'include',
      })
    }
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new ApiError(response.status, response.statusText, data)
  }

  return response.json()
}

// Convenience methods for Core API
export const coreApi = {
  get: <T>(endpoint: string, auth = true) =>
    apiRequest<T>(CORE_API_URL, endpoint, { method: 'GET', auth }),

  post: <T>(endpoint: string, body?: unknown, auth = true) =>
    apiRequest<T>(CORE_API_URL, endpoint, { method: 'POST', body, auth }),

  put: <T>(endpoint: string, body?: unknown, auth = true) =>
    apiRequest<T>(CORE_API_URL, endpoint, { method: 'PUT', body, auth }),

  delete: <T>(endpoint: string, auth = true) =>
    apiRequest<T>(CORE_API_URL, endpoint, { method: 'DELETE', auth }),

  upload: <T>(endpoint: string, formData: FormData, auth = true) =>
    uploadRequest<T>(CORE_API_URL, endpoint, formData, auth),
}

// Convenience methods for Orchestrator
export const orchestratorApi = {
  get: <T>(endpoint: string, auth = true) =>
    apiRequest<T>(ORCHESTRATOR_URL, endpoint, { method: 'GET', auth }),

  post: <T>(endpoint: string, body?: unknown, auth = true) =>
    apiRequest<T>(ORCHESTRATOR_URL, endpoint, { method: 'POST', body, auth }),

  upload: <T>(endpoint: string, formData: FormData, auth = true) =>
    uploadRequest<T>(ORCHESTRATOR_URL, endpoint, formData, auth),

  delete: <T>(endpoint: string, auth = true) =>
    apiRequest<T>(ORCHESTRATOR_URL, endpoint, { method: 'DELETE', auth }),
}
