import { coreApi } from './client'

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
