// API Client
export { coreApi, orchestratorApi, ApiError, CORE_API_URL, ORCHESTRATOR_URL } from './client'

// Core API endpoints
export { auth, config, steps, artifacts } from './coreApi'
export type {
  RegisterRequest,
  RegisterResponse,
  LoginRequest,
  LoginResponse,
  User,
  ConfigField,
  ConfigGroup,
  ConfigInfo,
  Config,
  CreateConfigRequest,
  StepEvent,
  Artifact,
} from './coreApi'

// Orchestrator endpoints
export { chat, createSSEConnection, createAuthenticatedSSEStream } from './orchestrator'
export type {
  StartChatRequest,
  ImproveRequest,
  SSEEvent,
  StepType,
  SSEConnectionOptions,
} from './orchestrator'
