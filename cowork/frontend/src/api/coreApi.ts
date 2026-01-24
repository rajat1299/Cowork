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

// ============ History/Sessions Types ============

export interface HistoryTask {
  id: number | string
  task_id: string
  project_id: string
  question: string
  language?: string
  model_platform?: string
  model_type?: string
  project_name?: string
  summary?: string
  tokens: number
  status: number // 1 = ongoing, 2 = done
  created_at?: string
  updated_at?: string
}

export interface ProjectGroup {
  project_id: string
  project_name?: string
  total_tokens: number
  task_count: number
  latest_task_date: string
  last_prompt: string
  tasks: HistoryTask[]
  total_completed_tasks: number
  total_ongoing_tasks: number
}

export interface HistoryListResponse {
  items: HistoryTask[]
  total: number
  page?: number
  size?: number
}

export interface GroupedHistoryResponse {
  projects: ProjectGroup[]
  total_projects: number
  total_tasks: number
  total_tokens: number
}

// ============ Provider Types ============

/**
 * Provider response from backend
 * Note: api_key is NEVER returned - use api_key_last4 and api_key_set instead
 */
export interface Provider {
  id: number
  provider_name: string
  model_type?: string
  endpoint_url?: string
  is_valid?: boolean
  prefer?: boolean
  encrypted_config?: Record<string, string>
  // Security: raw api_key is never returned
  api_key_last4?: string  // Last 4 chars of key for display
  api_key_set?: boolean   // Whether a key has been saved
  created_at?: string
  updated_at?: string
}

/**
 * Create provider request
 * Backend handles default endpoints based on provider_name
 */
export interface CreateProviderRequest {
  provider_name: string
  api_key: string
  model_type?: string
  endpoint_url?: string  // Optional - backend has defaults per provider
  is_valid?: boolean
  prefer?: boolean
  encrypted_config?: Record<string, string>
}

/**
 * Update provider request
 * Omit api_key if you don't want to rotate it
 */
export interface UpdateProviderRequest {
  provider_name?: string
  api_key?: string  // Only include if rotating key
  model_type?: string
  endpoint_url?: string
  is_valid?: boolean
  prefer?: boolean
  encrypted_config?: Record<string, string>
}

export interface ValidateModelRequest {
  model_platform: string
  model_type: string
  api_key: string
  url?: string
  extra_params?: Record<string, string>
}

export interface ValidateModelResponse {
  is_valid: boolean
  is_tool_calls?: boolean
  message?: string
  error?: string
}

// ============ Provider Endpoints ============

export const providers = {
  /**
   * Get all providers for the current user
   */
  list: (): Promise<Provider[]> =>
    coreApi.get('/providers'),

  /**
   * Get a single provider by ID
   */
  get: (id: number): Promise<Provider> =>
    coreApi.get(`/provider/${id}`),

  /**
   * Create a new provider
   */
  create: (data: CreateProviderRequest): Promise<Provider> =>
    coreApi.post('/provider', data),

  /**
   * Update an existing provider
   */
  update: (id: number, data: UpdateProviderRequest): Promise<Provider> =>
    coreApi.put(`/provider/${id}`, data),

  /**
   * Delete a provider
   */
  delete: (id: number): Promise<void> =>
    coreApi.delete(`/provider/${id}`),

  /**
   * Set a provider as preferred/default
   */
  setPreferred: (providerId: number): Promise<void> =>
    coreApi.post('/provider/prefer', { provider_id: providerId }),

  /**
   * Validate a model configuration
   */
  validate: (data: ValidateModelRequest): Promise<ValidateModelResponse> =>
    coreApi.post('/model/validate', data, false),
}

// ============ History/Sessions Endpoints ============

export const history = {
  /**
   * Get flat list of history tasks
   */
  list: (limit?: number, offset?: number, projectId?: string): Promise<HistoryTask[]> => {
    const params = new URLSearchParams()
    if (limit !== undefined) params.set('limit', String(limit))
    if (offset !== undefined) params.set('offset', String(offset))
    if (projectId) params.set('project_id', projectId)
    const query = params.toString()
    return coreApi.get(`/chat/histories${query ? `?${query}` : ''}`)
  },

  /**
   * Get history grouped by project
   */
  listGrouped: (includeTasks = true): Promise<GroupedHistoryResponse> =>
    coreApi.get(`/chat/histories/grouped?include_tasks=${includeTasks}`),

  /**
   * Get single history task by task_id
   */
  getByTaskId: (taskId: string): Promise<HistoryTask> =>
    coreApi.get(`/chat/history?task_id=${taskId}`),

  /**
   * Get single history task by ID
   */
  get: (historyId: number): Promise<HistoryTask> =>
    coreApi.get(`/chat/history/${historyId}`),

  /**
   * Delete history task
   */
  delete: (historyId: number): Promise<void> =>
    coreApi.delete(`/chat/history/${historyId}`),
}

// ============ Share Types ============

export interface ShareCreateRequest {
  task_id: string
}

export interface ShareTokenResponse {
  token: string
  expires_at: string
}

export interface ShareInfo {
  question: string
  language: string
  model_platform: string
  model_type: string
  max_retries: number
  project_name?: string
  summary?: string
}

// ============ Share Endpoints ============

export const share = {
  /**
   * Create a share link for a task (requires auth)
   */
  create: (taskId: string): Promise<ShareTokenResponse> =>
    coreApi.post('/chat/share', { task_id: taskId }),

  /**
   * Get share info by token (public, no auth required)
   */
  getInfo: (token: string): Promise<ShareInfo> =>
    coreApi.get(`/chat/share/info/${token}`, false),
}
