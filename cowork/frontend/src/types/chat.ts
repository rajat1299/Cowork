/**
 * Chat and SSE types for Cowork
 * Based on backend SSE contract and reference project patterns
 */

// ============ Step Types ============

/**
 * SSE step types from backend
 * These align with the reference project + our backend's step types
 */
export type StepType =
  // Task lifecycle
  | 'confirmed'           // Task confirmed, starting processing
  | 'decompose_text'      // Streaming task decomposition
  | 'to_sub_tasks'        // Task split into subtasks
  | 'task_state'          // Task state change
  // Agent lifecycle
  | 'create_agent'        // New agent created
  | 'activate_agent'      // Agent becomes active
  | 'deactivate_agent'    // Agent finished
  | 'assign_task'         // Task assigned to agent
  // Toolkit/tool lifecycle
  | 'activate_toolkit'    // Tool execution started
  | 'deactivate_toolkit'  // Tool execution finished
  // Streaming
  | 'streaming'           // Partial response chunk
  // Artifacts
  | 'artifact'            // Artifact created
  | 'write_file'          // File written
  // Completion
  | 'end'                 // Task completed
  | 'error'               // Error occurred
  // User interaction
  | 'ask'                 // Agent asks user a question
  | 'ask_user'            // Agent asks user a question (normalized)
  | 'wait_confirm'        // Waiting for user confirmation
  | 'turn_cancelled'      // Turn cancelled
  // System
  | 'notice'              // System notice
  | 'context_too_long'    // Context limit exceeded
  | 'budget_not_enough'   // Budget exhausted

// ============ SSE Event Types ============

/**
 * Base SSE event structure from backend
 */
export interface SSEEvent<T = Record<string, unknown>> {
  task_id: string
  step: StepType
  data: T & { agent_event?: AgentEvent }
  timestamp: number
}

export interface AgentEvent {
  type: string
  payload?: Record<string, unknown>
  timestamp_ms?: number
  turn_id?: string
  session_id?: string
  event_id?: string
}

/**
 * Data payloads for specific step types
 */
export interface ConfirmedData {
  question: string
  project_id?: string
}

export interface StreamingData {
  chunk: string
}

export interface DecomposeTextData {
  content: string
}

export interface SubTasksData {
  sub_tasks: TaskInfo[]
  summary_task?: string
}

export interface AgentData {
  agent_id: string
  agent_name: string
  tools?: string[]  // Optional for safety, but should be present
  task_id?: string
}

export interface AssignTaskData {
  assignee_id: string  // Maps to agent_id from create_agent
  task_id: string
  content: string
  state: 'waiting' | 'running' | 'DONE' | 'FAILED'
  failure_count: number
}

export interface ToolkitData {
  agent_name: string           // Used for correlation (not agent_id)
  process_task_id: string      // Subtask ID
  toolkit_name: string
  method_name: string
  message: string              // args/kwargs as string
  output?: string              // Present in deactivate_toolkit
  result?: string
}

export interface ArtifactData {
  id: string
  type: 'file' | 'code' | 'image'
  name: string
  content_url?: string
}

export interface EndData {
  result?: string
  answer?: string
  tokens?: number
}

export interface ErrorData {
  message: string
  code?: string
}

export interface AskData {
  question: string
  agent_id?: string
}

export interface TaskStateData {
  task_id: string
  state: 'running' | 'completed' | 'failed' | 'paused'
}

export interface ContextTooLongData {
  current_length: number
  max_length: number
}

export interface NoticeData {
  message: string
  type?: 'compacting' | 'info' | 'warning'
  progress?: number
}

// ============ Chat/Message Types ============

export type MessageRole = 'user' | 'assistant' | 'system'

export interface Message {
  id: string
  role: MessageRole
  content: string
  timestamp: number
  isStreaming?: boolean
  // For tool/agent messages
  agentName?: string
  toolName?: string
  // For artifacts
  artifacts?: ArtifactInfo[]
  // For attachments
  attachments?: AttachmentInfo[]
}

export interface ArtifactInfo {
  id: string
  type: 'file' | 'code' | 'image' | 'viewed' | 'created'
  name: string
  contentUrl?: string
  action?: 'created' | 'viewed' | 'modified'
}

export interface AttachmentInfo {
  id: string
  name: string
  size: number
  contentType?: string
  url?: string
  path?: string
  kind?: 'image' | 'file'
  previewUrl?: string
}

// ============ Task Types ============

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'paused'

export interface TaskInfo {
  id: string
  title: string
  status: TaskStatus
  assignee?: string        // agent_id from assign_task.assignee_id
  failureCount?: number    // From assign_task.failure_count
}

export interface AgentInfo {
  id: string
  name: string
  status: 'idle' | 'active' | 'finished'
  tasks: TaskInfo[]
  tools?: string[]  // From create_agent event
}

// ============ Chat State Types ============

export interface ChatTask {
  id: string
  projectId: string
  messages: Message[]
  status: TaskStatus
  // Task decomposition
  subtasks: TaskInfo[]
  streamingDecomposeText: string
  // Agents
  activeAgents: AgentInfo[]
  // Progress
  currentStep: StepType | null
  progressSteps: ProgressStep[]
  // Artifacts
  artifacts: ArtifactInfo[]
  // Metadata
  tokens: number
  startTime: number
  endTime?: number
  // Error state
  error?: string
  isContextExceeded?: boolean
  // Notice state (for compacting, etc.)
  notice?: NoticeData | null
}

export interface ProgressStep {
  step: StepType
  label: string
  status: 'pending' | 'active' | 'completed' | 'failed'
  timestamp?: number
  data?: Record<string, unknown>
}

// ============ Chat Request Types ============

/** Agent configuration for custom tool selection */
export interface AgentConfig {
  name: string
  tools: string[]
}

export interface StartChatRequest {
  project_id: string
  task_id: string
  question: string
  // Model selection (BYOK)
  model_provider?: string
  model_type?: string
  api_key?: string
  api_url?: string
  // Context
  attachments?: AttachmentPayload[]
  language?: string
  // Features
  search_enabled?: boolean
  agents?: AgentConfig[]
}

export interface ImproveChatRequest {
  question: string
  task_id?: string
  // Features (same as StartChatRequest)
  search_enabled?: boolean
  attachments?: AttachmentPayload[]
  agents?: AgentConfig[]
}

export interface AttachmentPayload {
  id?: string
  name: string
  path: string
  content_type?: string
  size?: number
  url?: string
}

// ============ Utility Functions ============

export function generateId(): string {
  return crypto.randomUUID()
}

export function createMessage(
  role: MessageRole,
  content: string,
  extras?: Partial<Message>
): Message {
  return {
    id: generateId(),
    role,
    content,
    timestamp: Date.now(),
    ...extras,
  }
}

/**
 * Get human-readable label for a step type
 */
export function getStepLabel(step: StepType): string {
  const labels: Record<StepType, string> = {
    confirmed: 'Task confirmed',
    decompose_text: 'Analyzing task',
    to_sub_tasks: 'Breaking down task',
    task_state: 'Task state changed',
    create_agent: 'Creating agent',
    activate_agent: 'Agent working',
    deactivate_agent: 'Agent finished',
    assign_task: 'Assigning task',
    activate_toolkit: 'Using tool',
    deactivate_toolkit: 'Tool finished',
    streaming: 'Generating response',
    artifact: 'Creating artifact',
    write_file: 'Writing file',
    end: 'Completed',
    error: 'Error',
    ask: 'Asking question',
    ask_user: 'Asking question',
    wait_confirm: 'Waiting for confirmation',
    turn_cancelled: 'Cancelled',
    notice: 'Notice',
    context_too_long: 'Context limit exceeded',
    budget_not_enough: 'Budget exhausted',
  }
  return labels[step] || step
}
