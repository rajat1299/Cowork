import { useCallback, useMemo } from 'react'
import { useChatStore } from '../stores/chatStore'
import { startSSEConnection, stopSSEConnection } from '../lib/sse'
import { buildTurnExecutionView, mapBackendStepToProgressStep } from '../lib/execution'
import { dedupeArtifactsByCanonicalName, filterUserArtifacts, normalizeArtifactUrl } from '../lib/artifacts'
import { emitTelemetryEvent } from '../lib/telemetry'
import { generateId, createMessage } from '../types/chat'
import { history, chatMessages, steps, artifacts as artifactsApi } from '../api/coreApi'
import { files as orchestratorFiles } from '../api/orchestrator'
import { ORCHESTRATOR_URL } from '../api/client'
import { useSessionStore } from '../stores/sessionStore'
import type {
  ChatTask,
  Message,
  ProgressStep,
  ArtifactInfo,
  AgentConfig,
  AttachmentInfo,
  AttachmentPayload,
} from '../types/chat'

/** Options for sending a chat message */
export interface ChatMessageOptions {
  searchEnabled?: boolean
  agents?: AgentConfig[]
  files?: File[]
}

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
  sendMessage: (message: string, options?: ChatMessageOptions & { projectId?: string }) => Promise<void>
  sendFollowUp: (message: string, options?: ChatMessageOptions) => Promise<void>
  stopTask: () => void
  clearChat: () => void
  resetActiveChat: () => void

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
  // Use individual selectors to avoid re-renders on unrelated state changes
  const activeTaskId = useChatStore((s) => s.activeTaskId)
  const activeProjectId = useChatStore((s) => s.activeProjectId)
  const tasks = useChatStore((s) => s.tasks)
  const isConnecting = useChatStore((s) => s.isConnecting)

  // Get stable action references (these don't change)
  const createTask = useChatStore((s) => s.createTask)
  const setActiveTask = useChatStore((s) => s.setActiveTask)
  const resetActiveChat = useChatStore((s) => s.resetActiveChat)
  const addMessage = useChatStore((s) => s.addMessage)
  const stopTaskAction = useChatStore((s) => s.stopTask)
  const clearTasks = useChatStore((s) => s.clearTasks)

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
    return dedupeArtifactsByCanonicalName(filterUserArtifacts(activeTask?.artifacts || []))
  }, [activeTask])

  const currentStep = useMemo(() => {
    return activeTask?.currentStep || null
  }, [activeTask])

  const error = useMemo(() => {
    return activeTask?.error
  }, [activeTask])

  const uploadChatFiles = useCallback(
    async (projectId: string, taskId: string, files: File[]): Promise<{
      attachments: AttachmentInfo[]
      payloads: AttachmentPayload[]
    }> => {
      if (files.length === 0) {
        return { attachments: [], payloads: [] }
      }
      const formData = new FormData()
      formData.append('project_id', projectId)
      formData.append('task_id', taskId)
      files.forEach((file) => formData.append('files', file))

      const response = await orchestratorFiles.upload(formData)
      const attachments: AttachmentInfo[] = response.files.map((file) => ({
        id: file.id,
        name: file.name,
        size: file.size,
        contentType: file.content_type,
        url: `${ORCHESTRATOR_URL}${file.url}`,
        path: file.path,
        kind: file.content_type?.startsWith('image/') ? 'image' : 'file',
      }))
      const payloads: AttachmentPayload[] = response.files.map((file) => ({
        id: file.id,
        name: file.name,
        path: file.path,
        content_type: file.content_type,
        size: file.size,
        url: file.url,
      }))
      return { attachments, payloads }
    },
    []
  )

  // Create a new chat/task
  const createNewChat = useCallback(
    (projectId?: string, question?: string): string => {
      const pid = projectId || generateId()
      const q = question || ''
      return createTask(pid, q)
    },
    [createTask]
  )

  // Send a new message (starts SSE connection)
  const sendMessage = useCallback(
    async (message: string, options?: ChatMessageOptions & { projectId?: string }): Promise<void> => {
      if (!options?.projectId && !activeTaskId && activeProjectId) {
        emitTelemetryEvent('welcome_send_ignored_stale_project_id', {
          stale_project_id: activeProjectId,
        })
      }

      const pid = options?.projectId || generateId()
      const taskId = generateId()
      let attachments: AttachmentInfo[] = []
      let attachmentPayloads: AttachmentPayload[] = []

      if (options?.files?.length) {
        const uploadResult = await uploadChatFiles(pid, taskId, options.files)
        attachments = uploadResult.attachments
        attachmentPayloads = uploadResult.payloads
      }

      createTask(pid, message, attachments, taskId)
      useSessionStore.getState().syncLocalSessions()
      void useSessionStore.getState().refreshSessionsBackground()

      try {
        await startSSEConnection({
          projectId: pid,
          taskId,
          question: message,
          searchEnabled: options?.searchEnabled,
          agents: options?.agents,
          attachments: attachmentPayloads,
          onError: (err) => {
            console.error('[useChat] SSE error:', err)
          },
        })
      } catch (err) {
        console.error('[useChat] Failed to start chat:', err)
        throw err
      }
    },
    [activeProjectId, activeTaskId, createTask, uploadChatFiles]
  )

  // Send a follow-up message to existing conversation
  const sendFollowUp = useCallback(
    async (message: string, options?: ChatMessageOptions): Promise<void> => {
      if (!activeProjectId || !activeTaskId) {
        // No active conversation, start a new one
        await sendMessage(message, options)
        return
      }

      let attachments: AttachmentInfo[] = []
      let attachmentPayloads: AttachmentPayload[] = []
      if (options?.files?.length) {
        const uploadResult = await uploadChatFiles(activeProjectId, activeTaskId, options.files)
        attachments = uploadResult.attachments
        attachmentPayloads = uploadResult.payloads
      }

      // Add user message to current task
      addMessage(activeTaskId, {
        id: generateId(),
        role: 'user',
        content: message,
        timestamp: Date.now(),
        attachments,
      })
      useSessionStore.getState().syncLocalSessions()
      void useSessionStore.getState().refreshSessionsBackground()

      try {
        useChatStore.setState((state) => {
          const task = state.tasks[activeTaskId]
          if (!task) return state
          return {
            tasks: {
              ...state.tasks,
              [activeTaskId]: {
                ...task,
                status: 'pending',
                currentStep: null,
                error: undefined,
                notice: null,
                streamingDecomposeText: '',
                subtasks: [],
                activeAgents: [],
              },
            },
          }
        })

        await startSSEConnection({
          projectId: activeProjectId,
          taskId: activeTaskId,
          question: message,
          searchEnabled: options?.searchEnabled,
          agents: options?.agents,
          attachments: attachmentPayloads,
          onError: (err) => {
            console.error('[useChat] Follow-up SSE error:', err)
          },
        })
      } catch (err) {
        console.error('[useChat] Failed to send follow-up:', err)
        throw err
      }
    },
    [activeProjectId, activeTaskId, addMessage, sendMessage, uploadChatFiles]
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

      const toOrchestratorUrl = (url?: string): string | undefined => {
        if (!url) return undefined
        if (url.startsWith('http://') || url.startsWith('https://')) return url
        return `${ORCHESTRATOR_URL}${url.startsWith('/') ? '' : '/'}${url}`
      }

      // Fetch full conversation messages from /chat/messages endpoint
      let messages: Message[] = []
      try {
        let chatMsgs = await chatMessages.listByTask(taskId)
        if (chatMsgs.length === 0) {
          chatMsgs = await chatMessages.listByProject(historyTask.project_id)
            .then((rows) => rows.filter((row) => row.task_id === taskId))
        }

        const mapAttachments = (metadata: Record<string, unknown> | null | undefined) => {
          const raw = metadata?.attachments
          if (!Array.isArray(raw)) return undefined
          const mapped = raw
            .filter((item) => item && typeof item === 'object')
            .map((item) => {
              const data = item as Record<string, unknown>
              const contentType = (data.content_type || data.contentType) as string | undefined
              const url = typeof data.url === 'string' ? data.url : undefined
              return {
                id: String(data.id || generateId()),
                name: String(data.name || 'attachment'),
                size: typeof data.size === 'number' ? data.size : 0,
                contentType,
                url: toOrchestratorUrl(url),
                path: typeof data.path === 'string' ? data.path : undefined,
                kind: contentType?.startsWith('image/') ? 'image' : 'file',
              } as AttachmentInfo
            })
          return mapped.length > 0 ? mapped : undefined
        }

        // Convert backend messages to frontend Message format
        messages = chatMsgs
          .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
          .map((msg) => ({
            id: String(msg.id),
            role: msg.role as 'user' | 'assistant' | 'system',
            content: msg.content,
            timestamp: new Date(msg.created_at).getTime(),
            agentName: msg.metadata?.agent_name as string | undefined,
            attachments: mapAttachments(msg.metadata),
          }))
      } catch (msgError) {
        console.warn('Failed to fetch chat messages, falling back to summary:', msgError)
        // Fallback: use question + summary if messages endpoint fails
        messages = [
          createMessage('user', historyTask.question),
          ...(historyTask.summary ? [createMessage('assistant', historyTask.summary)] : [])
        ]
      }

      const [stepsResult, artifactsResult] = await Promise.allSettled([
        steps.list(taskId),
        artifactsApi.list(taskId),
      ])

      const progressSteps = stepsResult.status === 'fulfilled'
        ? stepsResult.value
            .sort((a, b) => Number(a.timestamp || 0) - Number(b.timestamp || 0))
            .map(mapBackendStepToProgressStep)
        : []

      const artifactsFromApi = artifactsResult.status === 'fulfilled'
        ? dedupeArtifactsByCanonicalName(
            filterUserArtifacts(
            artifactsResult.value.map((artifact) => ({
              id: artifact.id,
              type: (artifact.type as ArtifactInfo['type']) || 'file',
              name: artifact.name,
              contentUrl: normalizeArtifactUrl(artifact.content_url),
              createdAt: new Date(artifact.created_at).getTime(),
            }))
            )
          )
        : []

      const artifactsFromSteps = progressSteps
        .filter((step) => step.step === 'artifact')
        .map((step, index) => {
          const data = step.data || {}
          const stepId = typeof data.id === 'string' ? data.id : `artifact-step-${index}`
          const contentUrl = typeof data.content_url === 'string' ? data.content_url : undefined
          const path = typeof data.path === 'string' ? data.path : undefined
          return {
            id: stepId,
            type: (typeof data.type === 'string' ? data.type : 'file') as ArtifactInfo['type'],
            name: typeof data.name === 'string' ? data.name : `artifact-${index + 1}`,
            contentUrl: normalizeArtifactUrl(contentUrl, path),
            path,
            createdAt: step.timestamp,
            action: (typeof data.action === 'string' ? data.action : 'created') as ArtifactInfo['action'],
          }
        })
      const filteredArtifactsFromSteps = dedupeArtifactsByCanonicalName(
        filterUserArtifacts(artifactsFromSteps)
      )
      const mergedArtifacts = dedupeArtifactsByCanonicalName([
        ...artifactsFromApi,
        ...filteredArtifactsFromSteps,
      ])

      const executionView = buildTurnExecutionView(progressSteps)
      const lastStep = progressSteps[progressSteps.length - 1]?.step
      const status =
        historyTask.status === 2 || lastStep === 'end'
          ? 'completed'
          : lastStep === 'error' || lastStep === 'context_too_long'
          ? 'failed'
          : 'running'

      // Create task in store with the fetched data
      const newTask: ChatTask = {
        id: taskId,
        projectId: historyTask.project_id,
        messages,
        status,
        subtasks: executionView.subtasks,
        streamingDecomposeText: '',
        activeAgents: [],
        currentStep: progressSteps[progressSteps.length - 1]?.step || null,
        progressSteps,
        artifacts: mergedArtifacts,
        tokens: historyTask.tokens || 0,
        startTime: historyTask.created_at ? new Date(historyTask.created_at).getTime() : Date.now(),
        endTime:
          status === 'completed' || status === 'failed'
            ? historyTask.updated_at
              ? new Date(historyTask.updated_at).getTime()
              : Date.now()
            : undefined,
      }

      // Add task to store using internal method
      useChatStore.setState((state) => ({
        tasks: { ...state.tasks, [taskId]: newTask },
        activeProjectId: historyTask.project_id, // Set active project for follow-ups
      }))
      useSessionStore.getState().syncLocalSessions()
      void useSessionStore.getState().refreshSessionsBackground()

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
      useSessionStore.getState().syncLocalSessions()
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
    resetActiveChat,

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
    return dedupeArtifactsByCanonicalName(filterUserArtifacts(tasks[activeTaskId]?.artifacts || []))
  }, [activeTaskId, tasks])
}
