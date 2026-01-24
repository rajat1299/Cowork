import { create } from 'zustand'
import { history } from '../api/coreApi'
import type { HistoryTask, ProjectGroup } from '../api/coreApi'
import { useChatStore } from './chatStore'

// ============ Session Item Type ============

export interface SessionItem {
  id: string
  projectId: string
  title: string
  preview: string
  status: 'ongoing' | 'completed'
  tokens: number
  updatedAt: string
  taskCount: number
  isLocal?: boolean // True if from local chatStore, not from backend
  historyId?: number // Backend numeric ID for delete operations
}

// ============ Store State ============

interface SessionState {
  // Session list
  sessions: SessionItem[]
  isLoading: boolean
  error: string | null

  // Pagination
  hasMore: boolean
  page: number

  // Actions
  fetchSessions: () => Promise<void>
  fetchMoreSessions: () => Promise<void>
  refreshSessions: () => Promise<void>
  deleteSession: (sessionId: string) => Promise<void>
  clearError: () => void
}

// ============ Utility Functions ============

function truncateText(text: string, maxLength: number): string {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength - 3) + '...'
}

function historyTaskToSession(task: HistoryTask): SessionItem {
  return {
    id: task.task_id,
    projectId: task.project_id,
    title: task.project_name || truncateText(task.question, 50),
    preview: task.summary || truncateText(task.question, 100),
    status: task.status === 2 ? 'completed' : 'ongoing',
    tokens: task.tokens || 0,
    updatedAt: task.updated_at || task.created_at || new Date().toISOString(),
    taskCount: 1,
    isLocal: false,
    historyId: typeof task.id === 'number' ? task.id : undefined,
  }
}

function projectGroupToSession(group: ProjectGroup): SessionItem {
  return {
    id: group.project_id,
    projectId: group.project_id,
    title: group.project_name || truncateText(group.last_prompt, 50),
    preview: truncateText(group.last_prompt, 100),
    status: group.total_ongoing_tasks > 0 ? 'ongoing' : 'completed',
    tokens: group.total_tokens,
    updatedAt: group.latest_task_date,
    taskCount: group.task_count,
    isLocal: false,
  }
}

/**
 * Get local sessions from chatStore
 * These are tasks currently in memory that may not be synced to backend yet
 */
function getLocalSessions(): SessionItem[] {
  const chatState = useChatStore.getState()
  const tasks = Object.values(chatState.tasks)

  return tasks.map((task): SessionItem => {
    const firstMessage = task.messages[0]
    const question = firstMessage?.content || 'New conversation'

    return {
      id: task.id,
      projectId: task.projectId,
      title: truncateText(question, 50),
      preview: truncateText(question, 100),
      status: task.status === 'completed' || task.status === 'failed' ? 'completed' : 'ongoing',
      tokens: task.tokens,
      updatedAt: new Date(task.endTime || task.startTime).toISOString(),
      taskCount: 1,
      isLocal: true,
    }
  }).sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
}

/**
 * Merge local and remote sessions, deduplicating by ID
 * Local sessions take precedence for ongoing tasks
 */
function mergeSessions(local: SessionItem[], remote: SessionItem[]): SessionItem[] {
  const sessionMap = new Map<string, SessionItem>()

  // Add remote sessions first
  remote.forEach((session) => {
    sessionMap.set(session.id, session)
  })

  // Overlay local sessions (they have fresher state)
  local.forEach((session) => {
    const existing = sessionMap.get(session.id)
    // Local ongoing sessions should override remote
    if (!existing || session.status === 'ongoing') {
      sessionMap.set(session.id, session)
    }
  })

  // Sort by updatedAt descending
  return Array.from(sessionMap.values()).sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  )
}

// ============ Store Implementation ============

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  isLoading: false,
  error: null,
  hasMore: true,
  page: 1,

  fetchSessions: async () => {
    set({ isLoading: true, error: null })

    try {
      // Get local sessions first
      const localSessions = getLocalSessions()

      // Try to fetch from backend (silently fail if not available)
      let remoteSessions: SessionItem[] = []
      try {
        // Try grouped endpoint first for better UX
        const groupedResponse = await history.listGrouped(false)
        if (groupedResponse.projects) {
          remoteSessions = groupedResponse.projects.map(projectGroupToSession)
        }
      } catch {
        // Fall back to flat list
        try {
          const listResponse = await history.list(20, 0)
          if (Array.isArray(listResponse)) {
            remoteSessions = listResponse.map(historyTaskToSession)
          }
        } catch {
          // Backend not available - silently use local only
          // This is expected when history endpoints aren't implemented yet
        }
      }

      // Merge local and remote
      const mergedSessions = mergeSessions(localSessions, remoteSessions)

      set({
        sessions: mergedSessions,
        isLoading: false,
        hasMore: remoteSessions.length >= 20,
        page: 1,
      })
    } catch (error) {
      console.error('Failed to fetch sessions:', error)
      // Still show local sessions on error
      const localSessions = getLocalSessions()
      set({
        sessions: localSessions,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to load sessions',
      })
    }
  },

  fetchMoreSessions: async () => {
    const { isLoading, hasMore, page, sessions } = get()
    if (isLoading || !hasMore) return

    set({ isLoading: true })

    try {
      const nextPage = page + 1
      const offset = nextPage * 20
      const listResponse = await history.list(20, offset)

      if (Array.isArray(listResponse) && listResponse.length > 0) {
        const newSessions = listResponse.map(historyTaskToSession)
        const localSessions = getLocalSessions()
        const mergedSessions = mergeSessions(localSessions, [...sessions, ...newSessions])

        set({
          sessions: mergedSessions,
          page: nextPage,
          hasMore: listResponse.length >= 20,
          isLoading: false,
        })
      } else {
        set({ hasMore: false, isLoading: false })
      }
    } catch (error) {
      console.error('Failed to fetch more sessions:', error)
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to load more sessions',
      })
    }
  },

  refreshSessions: async () => {
    set({ page: 1, hasMore: true })
    await get().fetchSessions()
  },

  deleteSession: async (sessionId) => {
    // Find the session to get its backend historyId
    const session = get().sessions.find((s) => s.id === sessionId)

    if (session?.historyId) {
      try {
        // Delete from backend using numeric historyId
        await history.delete(session.historyId)
      } catch {
        // Backend might not have this session, that's OK
        console.warn('Could not delete session from backend:', sessionId)
      }
    }

    // Remove from local state
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== sessionId),
    }))

    // Also remove from chatStore if it exists there
    const chatStore = useChatStore.getState()
    if (chatStore.tasks[sessionId]) {
      chatStore.removeTask(sessionId)
    }
  },

  clearError: () => set({ error: null }),
}))

// ============ Format Helpers ============

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
