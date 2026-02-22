import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  Message,
  ChatTask,
  TaskStatus,
  StepType,
  ProgressStep,
  ArtifactInfo,
  TaskInfo,
  AgentInfo,
  NoticeData,
  AttachmentInfo,
} from '../types/chat'
import { generateId, createMessage, getStepLabel } from '../types/chat'
import { isBlockedArtifact } from '../lib/artifacts'

// ============ Active SSE Controllers ============
// Track active SSE connections per task for cleanup
const activeSSEControllers: Record<string, AbortController> = {}

export function getSSEController(taskId: string): AbortController | undefined {
  return activeSSEControllers[taskId]
}

export function setSSEController(taskId: string, controller: AbortController): void {
  // Abort existing controller if present
  if (activeSSEControllers[taskId]) {
    try {
      activeSSEControllers[taskId].abort()
    } catch (e) {
      console.warn('Error aborting existing SSE controller:', e)
    }
  }
  activeSSEControllers[taskId] = controller
}

export function removeSSEController(taskId: string): void {
  if (activeSSEControllers[taskId]) {
    try {
      activeSSEControllers[taskId].abort()
    } catch (e) {
      console.warn('Error aborting SSE controller:', e)
    }
    delete activeSSEControllers[taskId]
  }
}

// ============ Streaming Text Buffer ============
// Buffer for high-frequency streaming updates (throttled at 50ms)
const streamingBuffer: Record<string, string> = {}
const streamingTimers: Record<string, ReturnType<typeof setTimeout>> = {}

const TASK_PERSIST_TTL_MS = 24 * 60 * 60 * 1000

type PersistedChatState = {
  activeProjectId: string | null
  activeTaskId: string | null
  tasks: Record<string, ChatTask>
}

function pruneTasksByTtl(tasks: Record<string, ChatTask>, now: number = Date.now()): Record<string, ChatTask> {
  const next: Record<string, ChatTask> = {}
  const minTimestamp = now - TASK_PERSIST_TTL_MS

  Object.entries(tasks).forEach(([taskId, task]) => {
    const lastUpdated = typeof task.endTime === 'number' ? task.endTime : task.startTime
    if (typeof lastUpdated === 'number' && lastUpdated >= minTimestamp) {
      next[taskId] = task
    }
  })

  return next
}

function normalizePersistedState(
  state: Partial<PersistedChatState>,
  now: number = Date.now()
): PersistedChatState {
  const tasks = pruneTasksByTtl(state.tasks || {}, now)
  let activeTaskId = state.activeTaskId || null
  let activeProjectId = state.activeProjectId || null

  if (activeTaskId && !tasks[activeTaskId]) {
    activeTaskId = null
  }

  if (activeTaskId) {
    activeProjectId = tasks[activeTaskId]?.projectId || null
  } else if (activeProjectId) {
    const hasTaskForProject = Object.values(tasks).some((task) => task.projectId === activeProjectId)
    if (!hasTaskForProject) {
      activeProjectId = null
    }
  }

  return {
    activeProjectId,
    activeTaskId,
    tasks,
  }
}

// ============ Store State ============

interface ChatState {
  // Current active project/session
  activeProjectId: string | null
  activeTaskId: string | null

  // Tasks indexed by taskId
  tasks: Record<string, ChatTask>

  // Global loading state
  isConnecting: boolean

  // Actions - Task Management
  createTask: (
    projectId: string,
    question: string,
    attachments?: AttachmentInfo[],
    taskIdOverride?: string
  ) => string
  removeTask: (taskId: string) => void
  setActiveTask: (taskId: string | null) => void
  resetActiveChat: () => void

  // Actions - Message Management
  addMessage: (taskId: string, message: Message) => void
  updateMessage: (taskId: string, messageId: string, updates: Partial<Message>) => void
  appendToLastMessage: (taskId: string, chunk: string) => void

  // Actions - Task State
  setTaskStatus: (taskId: string, status: TaskStatus) => void
  setCurrentStep: (taskId: string, step: StepType | null) => void
  addProgressStep: (taskId: string, step: ProgressStep) => void
  updateProgressStep: (taskId: string, step: StepType, updates: Partial<ProgressStep>) => void

  // Actions - Streaming
  setStreamingDecomposeText: (taskId: string, text: string) => void
  clearStreamingDecomposeText: (taskId: string) => void

  // Actions - Subtasks & Agents
  setSubtasks: (taskId: string, subtasks: TaskInfo[]) => void
  updateSubtaskStatus: (taskId: string, subtaskId: string, status: TaskStatus) => void
  addAgent: (taskId: string, agent: AgentInfo) => void
  updateAgentStatus: (taskId: string, agentId: string, status: AgentInfo['status']) => void

  // Actions - Artifacts
  addArtifact: (taskId: string, artifact: ArtifactInfo) => void
  addArtifactToLatestAssistant: (taskId: string, artifact: ArtifactInfo) => void

  // Actions - Error & Metadata
  setTaskError: (taskId: string, error: string | undefined) => void
  setTaskTokens: (taskId: string, tokens: number) => void
  setContextExceeded: (taskId: string, exceeded: boolean) => void

  // Actions - Notice
  setNotice: (taskId: string, notice: NoticeData | null) => void

  // Actions - Connection State
  setConnecting: (connecting: boolean) => void

  // Actions - Stop/Cleanup
  stopTask: (taskId: string) => void
  clearTasks: () => void

  // Getters
  getTask: (taskId: string) => ChatTask | undefined
  getActiveTask: () => ChatTask | undefined
  getMessages: (taskId: string) => Message[]
}

// ============ Initial Task State ============

function createInitialTask(
  projectId: string,
  taskId: string,
  question: string,
  attachments?: AttachmentInfo[]
): ChatTask {
  return {
    id: taskId,
    projectId,
    messages: [createMessage('user', question, { attachments })],
    status: 'pending',
    subtasks: [],
    streamingDecomposeText: '',
    activeAgents: [],
    currentStep: null,
    progressSteps: [],
    artifacts: [],
    tokens: 0,
    startTime: Date.now(),
  }
}

// ============ Store Implementation ============

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      activeProjectId: null,
      activeTaskId: null,
      tasks: {},
      isConnecting: false,

      // Task Management
      createTask: (projectId, question, attachments, taskIdOverride) => {
        const taskId = taskIdOverride || generateId()
        const task = createInitialTask(projectId, taskId, question, attachments)

        set((state) => ({
          activeProjectId: projectId,
          activeTaskId: taskId,
          tasks: {
            ...state.tasks,
            [taskId]: task,
          },
        }))

        return taskId
      },

      removeTask: (taskId) => {
        // Cleanup SSE controller
        removeSSEController(taskId)

        // Clear streaming buffers
        delete streamingBuffer[taskId]
        if (streamingTimers[taskId]) {
          clearTimeout(streamingTimers[taskId])
          delete streamingTimers[taskId]
        }

        set((state) => {
          const remaining = { ...state.tasks }
          delete remaining[taskId]
          const removingActiveTask = state.activeTaskId === taskId
          return {
            tasks: remaining,
            activeTaskId: removingActiveTask ? null : state.activeTaskId,
            activeProjectId: removingActiveTask ? null : state.activeProjectId,
          }
        })
      },

      setActiveTask: (taskId) => {
        set((state) => {
          if (!taskId) {
            return {
              activeTaskId: null,
              activeProjectId: null,
            }
          }

          const task = state.tasks[taskId]
          if (!task) {
            return {
              activeTaskId: null,
              activeProjectId: null,
            }
          }

          return {
            activeTaskId: taskId,
            activeProjectId: task.projectId,
          }
        })
      },
      resetActiveChat: () => {
        set({
          activeTaskId: null,
          activeProjectId: null,
        })
      },

      // Message Management
      addMessage: (taskId, message) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                messages: [...task.messages, message],
              },
            },
          }
        })
      },

      updateMessage: (taskId, messageId, updates) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                messages: task.messages.map((msg) =>
                  msg.id === messageId ? { ...msg, ...updates } : msg
                ),
              },
            },
          }
        })
      },

      appendToLastMessage: (taskId, chunk) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task || task.messages.length === 0) return state

          const messages = [...task.messages]
          const lastMessage = messages[messages.length - 1]

          if (lastMessage.role === 'assistant') {
            messages[messages.length - 1] = {
              ...lastMessage,
              content: lastMessage.content + chunk,
            }
          }

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                messages,
              },
            },
          }
        })
      },

      // Task State
      setTaskStatus: (taskId, status) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                status,
                endTime: status === 'completed' || status === 'failed' ? Date.now() : task.endTime,
              },
            },
          }
        })
      },

      setCurrentStep: (taskId, step) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                currentStep: step,
              },
            },
          }
        })
      },

      addProgressStep: (taskId, progressStep) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                progressSteps: [...task.progressSteps, progressStep],
              },
            },
          }
        })
      },

      updateProgressStep: (taskId, step, updates) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                progressSteps: task.progressSteps.map((ps) =>
                  ps.step === step ? { ...ps, ...updates } : ps
                ),
              },
            },
          }
        })
      },

      // Streaming
      setStreamingDecomposeText: (taskId, text) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                streamingDecomposeText: text,
              },
            },
          }
        })
      },

      clearStreamingDecomposeText: (taskId) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                streamingDecomposeText: '',
              },
            },
          }
        })
      },

      // Subtasks & Agents
      setSubtasks: (taskId, subtasks) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                subtasks,
              },
            },
          }
        })
      },

      updateSubtaskStatus: (taskId, subtaskId, status) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                subtasks: task.subtasks.map((st) =>
                  st.id === subtaskId ? { ...st, status } : st
                ),
              },
            },
          }
        })
      },

      addAgent: (taskId, agent) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                activeAgents: [...task.activeAgents, agent],
              },
            },
          }
        })
      },

      updateAgentStatus: (taskId, agentId, status) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                activeAgents: task.activeAgents.map((agent) =>
                  agent.id === agentId ? { ...agent, status } : agent
                ),
              },
            },
          }
        })
      },

      // Artifacts
      addArtifact: (taskId, artifact) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state
          if (isBlockedArtifact(artifact)) return state

          const existingIndex = task.artifacts.findIndex((item) => item.id === artifact.id)
          const nextArtifacts =
            existingIndex >= 0
              ? task.artifacts.map((item, index) =>
                  index === existingIndex ? { ...item, ...artifact } : item
                )
              : [...task.artifacts, artifact]

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                artifacts: nextArtifacts,
              },
            },
          }
        })
      },

      addArtifactToLatestAssistant: (taskId, artifact) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state
          if (isBlockedArtifact(artifact)) return state

          const messages = [...task.messages]
          for (let i = messages.length - 1; i >= 0; i -= 1) {
            const message = messages[i]
            if (message.role !== 'assistant') continue
            const artifacts = message.artifacts || []
            const existingIndex = artifacts.findIndex((item) => item.id === artifact.id)
            const nextArtifacts =
              existingIndex >= 0
                ? artifacts.map((item, index) =>
                    index === existingIndex ? { ...item, ...artifact } : item
                  )
                : [...artifacts, artifact]
            messages[i] = {
              ...message,
              artifacts: nextArtifacts,
            }
            return {
              tasks: {
                ...state.tasks,
                [taskId]: {
                  ...task,
                  messages,
                },
              },
            }
          }

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                messages: [
                  ...messages,
                  createMessage('assistant', 'Generated artifact.', { artifacts: [artifact] }),
                ],
              },
            },
          }
        })
      },

      // Error & Metadata
      setTaskError: (taskId, error) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                error,
                status: error ? 'failed' : task.status,
              },
            },
          }
        })
      },

      setTaskTokens: (taskId, tokens) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                tokens,
              },
            },
          }
        })
      },

      setContextExceeded: (taskId, exceeded) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                isContextExceeded: exceeded,
                status: exceeded ? 'paused' : task.status,
              },
            },
          }
        })
      },

      // Notice
      setNotice: (taskId, notice) => {
        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                notice,
              },
            },
          }
        })
      },

      // Connection State
      setConnecting: (connecting) => {
        set({ isConnecting: connecting })
      },

      // Stop/Cleanup
      stopTask: (taskId) => {
        removeSSEController(taskId)

        set((state) => {
          const task = state.tasks[taskId]
          if (!task) return state

          return {
            tasks: {
              ...state.tasks,
              [taskId]: {
                ...task,
                status: 'completed',
                endTime: Date.now(),
              },
            },
          }
        })
      },

      clearTasks: () => {
        // Cleanup all SSE controllers
        Object.keys(activeSSEControllers).forEach(removeSSEController)

        set({
          tasks: {},
          activeTaskId: null,
          activeProjectId: null,
        })
      },

      // Getters
      getTask: (taskId) => get().tasks[taskId],

      getActiveTask: () => {
        const { activeTaskId, tasks } = get()
        return activeTaskId ? tasks[activeTaskId] : undefined
      },

      getMessages: (taskId) => {
        const task = get().tasks[taskId]
        return task?.messages || []
      },
    }),
    {
      name: 'cowork-chat',
      partialize: (state) => ({
        ...normalizePersistedState(state),
      }),
      merge: (persistedState, currentState) => ({
        ...currentState,
        ...normalizePersistedState((persistedState || {}) as Partial<PersistedChatState>),
      }),
    }
  )
)

// ============ Throttled Streaming Update ============

/**
 * Update streaming text with throttling to prevent excessive re-renders
 * Used for high-frequency events like decompose_text
 */
export function updateStreamingTextThrottled(
  taskId: string,
  text: string,
  append: boolean = false
): void {
  const store = useChatStore.getState()

  // Update buffer immediately
  if (append) {
    streamingBuffer[taskId] = (streamingBuffer[taskId] || '') + text
  } else {
    streamingBuffer[taskId] = text
  }

  // Throttle store updates to ~60fps (16ms)
  if (!streamingTimers[taskId]) {
    streamingTimers[taskId] = setTimeout(() => {
      const bufferedText = streamingBuffer[taskId]
      if (bufferedText !== undefined) {
        store.setStreamingDecomposeText(taskId, bufferedText)
      }
      delete streamingTimers[taskId]
    }, 16)
  }
}

// ============ Helper for Adding Progress Steps ============

export function addProgressStepFromEvent(
  taskId: string,
  step: StepType,
  status: ProgressStep['status'] = 'active',
  data?: Record<string, unknown>
): void {
  const store = useChatStore.getState()

  // Mark previous active steps as completed
  const task = store.getTask(taskId)
  if (task) {
    task.progressSteps
      .filter((ps) => ps.status === 'active')
      .forEach((ps) => {
        store.updateProgressStep(taskId, ps.step, { status: 'completed' })
      })
  }

  // Add new step
  store.addProgressStep(taskId, {
    step,
    label: getStepLabel(step),
    status,
    timestamp: Date.now(),
    data,
  })

  store.setCurrentStep(taskId, step)
}
