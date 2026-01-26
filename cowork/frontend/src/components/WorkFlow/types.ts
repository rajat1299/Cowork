/**
 * WorkFlow Component Types
 * 
 * Types for the workflow visualization component.
 * Maps SSE events to visual state.
 */

// ============ Agent Types ============

export type AgentType = 
  | 'developer_agent' 
  | 'search_agent' 
  | 'document_agent' 
  | 'multi_modal_agent'
  | string // Custom agents

export type AgentStatus = 'idle' | 'active' | 'done'

export interface WorkflowAgent {
  id: string
  name: string
  type: AgentType
  status: AgentStatus
  tools: string[]
  tasks: WorkflowTask[]
  toolkitActivity: ToolkitActivity[]
  // Metadata for animation
  activatedAt?: number
  deactivatedAt?: number
}

// ============ Task Types ============

export type TaskState = 'waiting' | 'running' | 'DONE' | 'FAILED' | 'completed' | 'failed'

export interface WorkflowTask {
  id: string
  content: string
  state: TaskState
  result?: string
  failureCount: number
  assigneeId?: string
  // For nested subtasks
  subtasks?: WorkflowTask[]
  parentId?: string
}

// ============ Toolkit Types ============

export type ToolkitStatus = 'running' | 'done'

export interface ToolkitActivity {
  id: string
  agentName: string
  processTaskId: string
  toolkitName: string
  methodName: string
  message: string
  status: ToolkitStatus
  timestamp: number
}

// ============ Workflow State ============

export interface WorkflowState {
  // All agents (created via create_agent events)
  agents: WorkflowAgent[]
  // All subtasks (from to_sub_tasks)
  tasks: WorkflowTask[]
  // Currently active agent (most recently activated)
  activeAgentId: string | null
  // Streaming decomposition text
  decomposeText: string
  // Overall workflow status
  status: 'idle' | 'decomposing' | 'running' | 'done' | 'error'
  // Summary from to_sub_tasks
  summaryTask: string
}

// ============ Component Props ============

export interface WorkFlowProps {
  /** Current workflow state derived from SSE events */
  agents: WorkflowAgent[]
  tasks: WorkflowTask[]
  activeAgentId: string | null
  decomposeText?: string
  status: WorkflowState['status']
  /** Callback when user clicks an agent card */
  onAgentSelect?: (agentId: string) => void
  /** Callback when user clicks a task */
  onTaskSelect?: (taskId: string) => void
  /** Optional className for container */
  className?: string
}

export interface AgentCardProps {
  agent: WorkflowAgent
  isActive: boolean
  isMuted: boolean
  onSelect?: () => void
  className?: string
}

export interface TaskPillProps {
  task: WorkflowTask
  onClick?: () => void
  className?: string
}

export interface ToolkitActivityProps {
  activity: ToolkitActivity
  className?: string
}

// ============ Helper Functions ============

/**
 * Get display name for agent type
 */
export function getAgentDisplayName(type: AgentType): string {
  const names: Record<string, string> = {
    developer_agent: 'Developer',
    search_agent: 'Search',
    document_agent: 'Document',
    multi_modal_agent: 'Multimodal',
  }
  return names[type] || type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

/**
 * Get CSS class for agent accent color
 */
export function getAgentAccentClass(type: AgentType): string {
  const classes: Record<string, string> = {
    developer_agent: 'agent-accent-developer',
    search_agent: 'agent-accent-search',
    document_agent: 'agent-accent-document',
    multi_modal_agent: 'agent-accent-multimodal',
  }
  return classes[type] || 'agent-accent-custom'
}

/**
 * Get icon name for agent type (to be used with lucide-react)
 */
export function getAgentIconName(type: AgentType): string {
  const icons: Record<string, string> = {
    developer_agent: 'Terminal',
    search_agent: 'Globe',
    document_agent: 'FileText',
    multi_modal_agent: 'Image',
  }
  return icons[type] || 'Bot'
}

/**
 * Normalize task state to our standard format
 */
export function normalizeTaskState(state: string): TaskState {
  const normalized = state.toLowerCase()
  if (normalized === 'done' || normalized === 'completed') return 'completed'
  if (normalized === 'failed') return 'failed'
  if (normalized === 'running') return 'running'
  return 'waiting'
}

/**
 * Check if task is complete (either done or failed)
 */
export function isTaskComplete(task: WorkflowTask): boolean {
  const state = normalizeTaskState(task.state)
  return state === 'completed' || state === 'failed'
}

/**
 * Get completion percentage for an agent's tasks
 */
export function getAgentProgress(agent: WorkflowAgent): number {
  if (agent.tasks.length === 0) return 0
  const completed = agent.tasks.filter(isTaskComplete).length
  return Math.round((completed / agent.tasks.length) * 100)
}

