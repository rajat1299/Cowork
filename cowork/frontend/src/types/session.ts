/**
 * Session/History types for Cowork
 * Based on backend API contract and reference project patterns
 */

// ============ Session Types ============

/**
 * Individual history/session task from backend
 */
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
  status: HistoryTaskStatus
  created_at?: string
  updated_at?: string
}

/**
 * Status enum matching backend
 * 1 = ongoing, 2 = done/completed
 */
export type HistoryTaskStatus = 1 | 2 | number

/**
 * Project group containing multiple tasks
 */
export interface ProjectGroup {
  project_id: string
  project_name?: string
  total_tokens: number
  task_count: number
  latest_task_date: string
  last_prompt: string
  tasks: HistoryTask[]
  // Additional metadata
  total_completed_tasks: number
  total_ongoing_tasks: number
}

/**
 * Grouped history response from backend
 */
export interface GroupedHistoryResponse {
  projects: ProjectGroup[]
  total_projects: number
  total_tasks: number
  total_tokens: number
}

/**
 * Flat history response (legacy/simple)
 */
export interface FlatHistoryResponse {
  items: HistoryTask[]
  total: number
  page?: number
  size?: number
}

// ============ Session Display Types ============

/**
 * Simplified session for sidebar display
 */
export interface SessionItem {
  id: string
  projectId: string
  title: string
  preview: string
  status: 'ongoing' | 'completed'
  tokens: number
  updatedAt: string
  taskCount: number
}

// ============ Utility Functions ============

/**
 * Convert HistoryTask to SessionItem for display
 */
export function historyTaskToSession(task: HistoryTask): SessionItem {
  return {
    id: task.task_id,
    projectId: task.project_id,
    title: task.project_name || truncateText(task.question, 50),
    preview: task.summary || truncateText(task.question, 100),
    status: task.status === 2 ? 'completed' : 'ongoing',
    tokens: task.tokens || 0,
    updatedAt: task.updated_at || task.created_at || new Date().toISOString(),
    taskCount: 1,
  }
}

/**
 * Convert ProjectGroup to SessionItem for display
 */
export function projectGroupToSession(group: ProjectGroup): SessionItem {
  return {
    id: group.project_id,
    projectId: group.project_id,
    title: group.project_name || truncateText(group.last_prompt, 50),
    preview: truncateText(group.last_prompt, 100),
    status: group.total_ongoing_tasks > 0 ? 'ongoing' : 'completed',
    tokens: group.total_tokens,
    updatedAt: group.latest_task_date,
    taskCount: group.task_count,
  }
}

/**
 * Truncate text with ellipsis
 */
function truncateText(text: string, maxLength: number): string {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength - 3) + '...'
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString()
}
