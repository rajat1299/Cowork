import { coreApi, CORE_API_URL } from './client'

// ============ Types ============

// Auth
export interface RegisterRequest {
  email: string
  password: string
}

export interface RegisterResponse {
  id: string
  email: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface User {
  id: string
  email: string
}

// OAuth
export type OAuthProvider = 'google' | 'github'

export interface OAuthTokenRequest {
  code: string
  state: string
  code_verifier?: string
}

export interface OAuthTokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

// Config
export interface ConfigField {
  key: string
  label?: string
  type?: string
  required?: boolean
}

export interface ConfigGroup {
  id: string
  name: string
  icon?: string
  fields: ConfigField[]
}

export interface ConfigInfo {
  groups?: ConfigGroup[]
  [key: string]: unknown
}

export interface Config {
  id: string
  group: string
  key: string
  value: string
  created_at?: string
  updated_at?: string
}

export interface CreateConfigRequest {
  group: string
  key: string
  value: string
}

// Steps
export interface StepEvent {
  id?: string
  task_id: string
  step: string
  data: Record<string, unknown>
  timestamp: number
}

// Artifacts
export interface Artifact {
  id: string
  task_id: string
  type: 'file' | 'code' | 'image' | string
  name: string
  content_url?: string
  created_at: string
}

// ============ Auth Endpoints ============

export const auth = {
  register: (data: RegisterRequest): Promise<RegisterResponse> =>
    coreApi.post('/auth/register', data, false),

  login: (data: LoginRequest): Promise<LoginResponse> =>
    coreApi.post('/auth/login', data, false),

  refresh: (refreshToken: string): Promise<LoginResponse> =>
    coreApi.post('/auth/refresh', { refresh_token: refreshToken }, false),

  me: (): Promise<User> =>
    coreApi.get('/auth/me'),
}

// ============ OAuth Endpoints ============

export const oauth = {
  /**
   * Build the OAuth login URL with PKCE parameters
   * This URL should be opened in a browser window
   */
  getLoginUrl: (
    provider: OAuthProvider,
    params: { state: string; codeChallenge: string }
  ): string => {
    const url = new URL(`${CORE_API_URL}/oauth/${provider}/login`)
    url.searchParams.set('state', params.state)
    url.searchParams.set('code_challenge', params.codeChallenge)
    url.searchParams.set('code_challenge_method', 'S256')
    return url.toString()
  },

  /**
   * Exchange OAuth code for tokens
   * Called after the OAuth callback with the authorization code
   */
  exchangeToken: (
    provider: OAuthProvider,
    data: OAuthTokenRequest
  ): Promise<OAuthTokenResponse> =>
    coreApi.post(`/oauth/${provider}/token`, data, false),
}

// ============ Config Endpoints ============

export const config = {
  getInfo: (): Promise<ConfigInfo> =>
    coreApi.get('/config/info'),

  list: (group?: string): Promise<Config[]> =>
    coreApi.get(group ? `/configs?group=${group}` : '/configs'),

  create: (data: CreateConfigRequest): Promise<Config> =>
    coreApi.post('/configs', data),

  update: (id: string, data: Partial<CreateConfigRequest>): Promise<Config> =>
    coreApi.put(`/configs/${id}`, data),

  delete: (id: string): Promise<void> =>
    coreApi.delete(`/configs/${id}`),
}

// ============ Steps Endpoints ============

export const steps = {
  list: (taskId: string): Promise<StepEvent[]> =>
    coreApi.get(`/chat/steps?task_id=${taskId}`),

  create: (data: StepEvent): Promise<StepEvent> =>
    coreApi.post('/chat/steps', data),
}

// ============ Artifacts Endpoints ============

export const artifacts = {
  list: (taskId: string): Promise<Artifact[]> =>
    coreApi.get(`/chat/artifacts?task_id=${taskId}`),

  create: (data: Omit<Artifact, 'id' | 'created_at'>): Promise<Artifact> =>
    coreApi.post('/chat/artifacts', data),
}
