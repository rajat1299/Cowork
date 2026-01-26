import { useCallback, useMemo } from 'react'
import { useChatStore } from '../stores/chatStore'
import { startSSEConnection, stopSSEConnection, sendImproveMessage } from '../lib/sse'
import { generateId, createMessage } from '../types/chat'
import { history, chatMessages } from '../api/coreApi'
import type { ChatTask, Message, ProgressStep, ArtifactInfo } from '../types/chat'

interface UseChatReturn {
  // State
  activeTask: ChatTask | undefined
  messages: Message[]
  isConnecting: boolean
  isRunning: boolean
  progressSteps: ProgressStep[]
  artifacts: ArtifactInfo[]
  currentStep: string | null
  error: string | undefined

  // Actions
  sendMessage: (message: string, projectId?: string) => Promise<void>
  sendFollowUp: (message: string) => Promise<void>
  stopTask: () => void
  clearChat: () => void

  // Task Management
  createNewChat: (projectId?: string, question?: string) => string
  switchTask: (taskId: string) => Promise<void>
  loadTask: (taskId: string) => Promise<boolean>
}

/**
 * Main hook for chat functionality
 * Provides access to chat state and actions
 */
export function useChat(): UseChatReturn {
  const store = useChatStore()

  const {
    activeTaskId,
    activeProjectId,
    tasks,
    isConnecting,
    createTask,
    setActiveTask,
    addMessage,
    stopTask: stopTaskAction,
    clearTasks,
  } = store

  // Derived state
  const activeTask = useMemo(() => {
    return activeTaskId ? tasks[activeTaskId] : undefined
  }, [activeTaskId, tasks])

  const messages = useMemo(() => {
    return activeTask?.messages || []
  }, [activeTask])

  const isRunning = useMemo(() => {
    return activeTask?.status === 'running' || activeTask?.status === 'pending'
  }, [activeTask])

  const progressSteps = useMemo(() => {
    return activeTask?.progressSteps || []
  }, [activeTask])

  const artifacts = useMemo(() => {
    return activeTask?.artifacts || []
  }, [activeTask])

  const currentStep = useMemo(() => {
    return activeTask?.currentStep || null
  }, [activeTask])

  const error = useMemo(() => {
    return activeTask?.error
  }, [activeTask])

  // Create a new chat/task
  const createNewChat = useCallback(
    (projectId?: string, question?: string): string => {
      const pid = projectId || activeProjectId || generateId()
      const q = question || ''
      return createTask(pid, q)
    },
    [activeProjectId, createTask]
  )

  // Send a new message (starts SSE connection)
  const sendMessage = useCallback(
    async (message: string, projectId?: string): Promise<void> => {
      const pid = projectId || activeProjectId || generateId()
      const taskId = createTask(pid, message)

      try {
        await startSSEConnection({
          projectId: pid,
          taskId,
          question: message,
          onError: (err) => {
            console.error('[useChat] SSE error:', err)
          },
        })
      } catch (err) {
        console.error('[useChat] Failed to start chat:', err)
        throw err
      }
    },
    [activeProjectId, createTask]
  )

  // Send a follow-up message to existing conversation
  const sendFollowUp = useCallback(
    async (message: string): Promise<void> => {
      if (!activeProjectId || !activeTaskId) {
        // No active conversation, start a new one
        await sendMessage(message)
        return
      }

      // Add user message to current task
      addMessage(activeTaskId, {
        id: generateId(),
        role: 'user',
        content: message,
        timestamp: Date.now(),
      })

      try {
        await sendImproveMessage(activeProjectId, message, activeTaskId)
      } catch (err) {
        console.error('[useChat] Failed to send follow-up:', err)
        throw err
      }
    },
    [activeProjectId, activeTaskId, addMessage, sendMessage]
  )

  // Stop the current task
  const stopTask = useCallback(() => {
    if (activeTaskId) {
      stopSSEConnection(activeTaskId)
      stopTaskAction(activeTaskId)
    }
  }, [activeTaskId, stopTaskAction])

  // Clear all chat history
  const clearChat = useCallback(() => {
    if (activeTaskId) {
      stopSSEConnection(activeTaskId)
    }
    clearTasks()
  }, [activeTaskId, clearTasks])

  // Load a task from backend into the store
  // Fetches full conversation history from /chat/messages endpoint
  const loadTask = useCallback(async (taskId: string): Promise<boolean> => {
    // Check if task already exists in store
    if (tasks[taskId]) {
      return true
    }

    try {
      // Fetch task metadata from backend
      const historyTask = await history.getByTaskId(taskId)

      // Fetch full conversation messages from /chat/messages endpoint
      let messages: Message[] = []
      try {
        const chatMsgs = await chatMessages.listByProject(historyTask.project_id)
        // Convert backend messages to frontend Message format
        messages = chatMsgs.map((msg) => ({
          id: String(msg.id),
          role: msg.role as 'user' | 'assistant' | 'system',
          content: msg.content,
          timestamp: new Date(msg.created_at).getTime(),
          agentName: msg.metadata?.agent_name as string | undefined,
        }))
      } catch (msgError) {
        console.warn('Failed to fetch chat messages, falling back to summary:', msgError)
        // Fallback: use question + summary if messages endpoint fails
        messages = [
          createMessage('user', historyTask.question),
          ...(historyTask.summary ? [createMessage('assistant', historyTask.summary)] : [])
        ]
      }

      // Create task in store with the fetched data
      const newTask: ChatTask = {
        id: taskId,
        projectId: historyTask.project_id,
        messages,
        status: historyTask.status === 2 ? 'completed' : 'running',
        subtasks: [],
        streamingDecomposeText: '',
        activeAgents: [],
        currentStep: null,
        progressSteps: [],
        artifacts: [],
        tokens: historyTask.tokens || 0,
        startTime: historyTask.created_at ? new Date(historyTask.created_at).getTime() : Date.now(),
        endTime: historyTask.status === 2 ? (historyTask.updated_at ? new Date(historyTask.updated_at).getTime() : Date.now()) : undefined,
      }

      // Add task to store using internal method
      useChatStore.setState((state) => ({
        tasks: { ...state.tasks, [taskId]: newTask },
        activeProjectId: historyTask.project_id, // Set active project for follow-ups
      }))

      return true
    } catch (error) {
      console.error('Failed to load task from backend:', error)
      return false
    }
  }, [tasks])

  // Switch to a different task, loading from backend if needed
  const switchTask = useCallback(
    async (taskId: string) => {
      // Try to load from backend if not in store
      if (!tasks[taskId]) {
        await loadTask(taskId)
      }
      setActiveTask(taskId)
    },
    [tasks, loadTask, setActiveTask]
  )

  return {
    // State
    activeTask,
    messages,
    isConnecting,
    isRunning,
    progressSteps,
    artifacts,
    currentStep,
    error,

    // Actions
    sendMessage,
    sendFollowUp,
    stopTask,
    clearChat,

    // Task Management
    createNewChat,
    switchTask,
    loadTask,
  }
}

/**
 * Hook for accessing a specific task by ID
 */
export function useChatTask(taskId: string | null) {
  const tasks = useChatStore((state) => state.tasks)

  return useMemo(() => {
    if (!taskId) return undefined
    return tasks[taskId]
  }, [taskId, tasks])
}

/**
 * Hook for accessing chat progress
 */
export function useChatProgress() {
  const activeTaskId = useChatStore((state) => state.activeTaskId)
  const tasks = useChatStore((state) => state.tasks)

  return useMemo(() => {
    if (!activeTaskId) return { steps: [], current: null }
    const task = tasks[activeTaskId]
    return {
      steps: task?.progressSteps || [],
      current: task?.currentStep || null,
      streamingText: task?.streamingDecomposeText || '',
      subtasks: task?.subtasks || [],
      agents: task?.activeAgents || [],
    }
  }, [activeTaskId, tasks])
}

/**
 * Hook for accessing chat artifacts
 */
export function useChatArtifacts() {
  const activeTaskId = useChatStore((state) => state.activeTaskId)
  const tasks = useChatStore((state) => state.tasks)

  return useMemo(() => {
    if (!activeTaskId) return []
    return tasks[activeTaskId]?.artifacts || []
  }, [activeTaskId, tasks])
}
