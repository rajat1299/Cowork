import { useCallback, useMemo } from 'react'
import { useChatStore } from '../stores/chatStore'
import { startSSEConnection, stopSSEConnection, sendImproveMessage } from '../lib/sse'
import { generateId } from '../types/chat'
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
  switchTask: (taskId: string) => void
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

  // Switch to a different task
  const switchTask = useCallback(
    (taskId: string) => {
      setActiveTask(taskId)
    },
    [setActiveTask]
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
