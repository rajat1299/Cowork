/**
 * SSE (Server-Sent Events) connection utility
 * Uses @microsoft/fetch-event-source for POST-based SSE
 */

import { fetchEventSource } from '@microsoft/fetch-event-source'
import { ORCHESTRATOR_URL } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import {
  useChatStore,
  setSSEController,
  removeSSEController,
  updateStreamingTextThrottled,
  addProgressStepFromEvent,
} from '../stores/chatStore'
import type {
  SSEEvent,
  StepType,
  StartChatRequest,
  ImproveChatRequest,
  ConfirmedData,
  StreamingData,
  DecomposeTextData,
  SubTasksData,
  AgentData,
  ToolkitData,
  ArtifactData,
  EndData,
  ErrorData,
  TaskStateData,
  ContextTooLongData,
} from '../types/chat'
import { createMessage, generateId } from '../types/chat'

// ============ Type Guards ============

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function hasStringProp(obj: Record<string, unknown>, key: string): boolean {
  return typeof obj[key] === 'string'
}

function asConfirmedData(data: unknown): ConfirmedData | null {
  if (!isRecord(data)) return null
  return data as unknown as ConfirmedData
}

function asStreamingData(data: unknown): StreamingData | null {
  if (!isRecord(data) || typeof data.chunk !== 'string') return null
  return data as unknown as StreamingData
}

function asDecomposeTextData(data: unknown): DecomposeTextData | null {
  if (!isRecord(data)) return null
  return data as unknown as DecomposeTextData
}

function asSubTasksData(data: unknown): SubTasksData | null {
  if (!isRecord(data)) return null
  return data as unknown as SubTasksData
}

function asAgentData(data: unknown): AgentData | null {
  if (!isRecord(data) || !hasStringProp(data, 'agent_id') || !hasStringProp(data, 'agent_name')) return null
  return data as unknown as AgentData
}

function asToolkitData(data: unknown): ToolkitData | null {
  if (!isRecord(data)) return null
  return data as unknown as ToolkitData
}

function asArtifactData(data: unknown): ArtifactData | null {
  if (!isRecord(data)) return null
  return data as unknown as ArtifactData
}

function asTaskStateData(data: unknown): TaskStateData | null {
  if (!isRecord(data) || !hasStringProp(data, 'state')) return null
  return data as unknown as TaskStateData
}

function asEndData(data: unknown): EndData | null {
  if (!isRecord(data)) return null
  return data as unknown as EndData
}

function asErrorData(data: unknown): ErrorData | null {
  if (!isRecord(data)) return null
  return data as unknown as ErrorData
}

function asContextTooLongData(data: unknown): ContextTooLongData | null {
  if (!isRecord(data)) return null
  return data as unknown as ContextTooLongData
}

// ============ SSE Connection Options ============

interface SSEConnectionOptions {
  projectId: string
  taskId: string
  question: string
  // Optional features
  searchEnabled?: boolean
  agents?: Array<{ name: string; tools: string[] }>
  attachments?: StartChatRequest['attachments']
  // Callbacks
  onOpen?: () => void
  onError?: (error: Error) => void
  onClose?: () => void
}

// ============ Event Handlers ============

/**
 * Handle SSE events based on step type
 */
function handleSSEEvent(taskId: string, event: SSEEvent): void {
  const { step, data } = event

  console.log(`[SSE] Step: ${step}`, data)

  switch (step) {
    case 'confirmed': {
      const typedData = asConfirmedData(data)
      if (typedData) handleConfirmed(taskId, typedData)
      break
    }

    case 'streaming': {
      const typedData = asStreamingData(data)
      if (typedData) handleStreaming(taskId, typedData)
      break
    }

    case 'decompose_text': {
      const typedData = asDecomposeTextData(data)
      if (typedData) handleDecomposeText(taskId, typedData)
      break
    }

    case 'to_sub_tasks': {
      const typedData = asSubTasksData(data)
      if (typedData) handleSubTasks(taskId, typedData)
      break
    }

    case 'create_agent':
    case 'activate_agent': {
      const typedData = asAgentData(data)
      if (typedData) handleAgentActivate(taskId, typedData, step)
      break
    }

    case 'deactivate_agent': {
      const typedData = asAgentData(data)
      if (typedData) handleAgentDeactivate(taskId, typedData)
      break
    }

    case 'activate_toolkit': {
      const typedData = asToolkitData(data)
      if (typedData) handleToolkitActivate(taskId, typedData)
      break
    }

    case 'deactivate_toolkit': {
      const typedData = asToolkitData(data)
      if (typedData) handleToolkitDeactivate(taskId, typedData)
      break
    }

    case 'artifact':
    case 'write_file': {
      const typedData = asArtifactData(data)
      if (typedData) handleArtifact(taskId, typedData)
      break
    }

    case 'task_state': {
      const typedData = asTaskStateData(data)
      if (typedData) handleTaskState(taskId, typedData)
      break
    }

    case 'end': {
      const typedData = asEndData(data)
      if (typedData) handleEnd(taskId, typedData)
      break
    }

    case 'error': {
      const typedData = asErrorData(data)
      if (typedData) handleError(taskId, typedData)
      break
    }

    case 'context_too_long': {
      const typedData = asContextTooLongData(data)
      if (typedData) handleContextTooLong(taskId, typedData)
      break
    }

    case 'ask':
      handleAsk(taskId, data as Record<string, unknown>)
      break

    case 'notice':
      handleNotice(taskId, data as Record<string, unknown>)
      break

    default:
      // Log unhandled step types for debugging
      console.log(`[SSE] Unhandled step type: ${step}`, data)
      addProgressStepFromEvent(taskId, step, 'active', data as Record<string, unknown>)
  }
}

// ============ Individual Event Handlers ============

function handleConfirmed(taskId: string, data: ConfirmedData): void {
  const store = useChatStore.getState()
  store.setTaskStatus(taskId, 'running')
  addProgressStepFromEvent(taskId, 'confirmed', 'completed', { question: data.question })
}

function handleStreaming(taskId: string, data: StreamingData): void {
  const store = useChatStore.getState()
  const task = store.getTask(taskId)

  if (!task) return

  // Clear any compacting notice when streaming resumes
  clearCompactingNotice(taskId)

  // Check if we have an assistant message to append to
  const lastMessage = task.messages[task.messages.length - 1]

  if (lastMessage?.role === 'assistant' && lastMessage.isStreaming) {
    // Append to existing streaming message
    store.appendToLastMessage(taskId, data.chunk)
  } else {
    // Create new streaming message
    store.addMessage(taskId, createMessage('assistant', data.chunk, { isStreaming: true }))
  }

  addProgressStepFromEvent(taskId, 'streaming', 'active')
}

function handleDecomposeText(taskId: string, data: DecomposeTextData): void {
  // Use throttled update for high-frequency streaming
  const content = data.content || ''

  // Determine if this is accumulated or delta format
  const currentText = useChatStore.getState().getTask(taskId)?.streamingDecomposeText || ''

  if (content.startsWith(currentText)) {
    // Accumulated: replace
    updateStreamingTextThrottled(taskId, content, false)
  } else {
    // Delta: append
    updateStreamingTextThrottled(taskId, content, true)
  }

  addProgressStepFromEvent(taskId, 'decompose_text', 'active')
}

function handleSubTasks(taskId: string, data: SubTasksData): void {
  const store = useChatStore.getState()

  // Clear streaming decompose text
  store.clearStreamingDecomposeText(taskId)

  // Set subtasks
  if (data.sub_tasks) {
    store.setSubtasks(
      taskId,
      data.sub_tasks.map((st) => ({
        id: st.id || generateId(),
        title: st.title,
        status: st.status || 'pending',
        assignee: st.assignee,
      }))
    )
  }

  addProgressStepFromEvent(taskId, 'to_sub_tasks', 'completed', { count: data.sub_tasks?.length })
}

function handleAgentActivate(taskId: string, data: AgentData, step: StepType): void {
  const store = useChatStore.getState()
  const task = store.getTask(taskId)

  if (!task) return

  const existingAgent = task.activeAgents.find((a) => a.id === data.agent_id)

  if (existingAgent) {
    store.updateAgentStatus(taskId, data.agent_id, 'active')
  } else {
    store.addAgent(taskId, {
      id: data.agent_id,
      name: data.agent_name,
      status: 'active',
      tasks: [],
    })
  }

  addProgressStepFromEvent(taskId, step, 'active', { agent: data.agent_name })
}

function handleAgentDeactivate(taskId: string, data: AgentData): void {
  const store = useChatStore.getState()
  store.updateAgentStatus(taskId, data.agent_id, 'finished')
  addProgressStepFromEvent(taskId, 'deactivate_agent', 'completed', { agent: data.agent_name })
}

function handleToolkitActivate(taskId: string, data: ToolkitData): void {
  addProgressStepFromEvent(taskId, 'activate_toolkit', 'active', {
    toolkit: data.toolkit_name,
    method: data.method_name,
  })
}

function handleToolkitDeactivate(taskId: string, data: ToolkitData): void {
  addProgressStepFromEvent(taskId, 'deactivate_toolkit', 'completed', {
    toolkit: data.toolkit_name,
    result: data.result,
  })
}

function handleArtifact(taskId: string, data: ArtifactData): void {
  const store = useChatStore.getState()

  store.addArtifact(taskId, {
    id: data.id || generateId(),
    type: data.type || 'file',
    name: data.name,
    contentUrl: data.content_url,
  })

  addProgressStepFromEvent(taskId, 'artifact', 'completed', { name: data.name })
}

function handleTaskState(taskId: string, data: TaskStateData): void {
  const store = useChatStore.getState()

  // Update subtask status if this is a subtask state change
  if (data.task_id && data.task_id !== taskId) {
    const statusMap: Record<string, 'pending' | 'running' | 'completed' | 'failed' | 'paused'> = {
      running: 'running',
      completed: 'completed',
      failed: 'failed',
      paused: 'paused',
    }
    store.updateSubtaskStatus(taskId, data.task_id, statusMap[data.state] || 'pending')
  }
}

function handleEnd(taskId: string, data: EndData): void {
  const store = useChatStore.getState()
  const task = store.getTask(taskId)

  if (!task) return

  // Clear any compacting notice
  clearCompactingNotice(taskId)

  // Finalize any streaming message
  const lastMessage = task.messages[task.messages.length - 1]
  if (lastMessage?.isStreaming) {
    store.updateMessage(taskId, lastMessage.id, { isStreaming: false })
  }

  // Add final answer if provided and different from last message
  if (data.answer && data.answer !== lastMessage?.content) {
    store.addMessage(taskId, createMessage('assistant', data.answer))
  } else if (data.result && data.result !== lastMessage?.content) {
    store.addMessage(taskId, createMessage('assistant', data.result))
  }

  // Update tokens if provided
  if (data.tokens) {
    store.setTaskTokens(taskId, data.tokens)
  }

  // Mark task as completed
  store.setTaskStatus(taskId, 'completed')
  addProgressStepFromEvent(taskId, 'end', 'completed', { tokens: data.tokens })

  // Cleanup SSE controller
  removeSSEController(taskId)
}

function handleError(taskId: string, data: ErrorData): void {
  const store = useChatStore.getState()

  const errorMessage = data.message || 'An error occurred'

  store.setTaskError(taskId, errorMessage)
  store.addMessage(taskId, createMessage('system', `Error: ${errorMessage}`))

  addProgressStepFromEvent(taskId, 'error', 'failed', { message: errorMessage })

  // Cleanup SSE controller
  removeSSEController(taskId)
}

function handleContextTooLong(taskId: string, data: ContextTooLongData): void {
  const store = useChatStore.getState()

  store.setContextExceeded(taskId, true)
  store.addMessage(
    taskId,
    createMessage(
      'system',
      `Context limit exceeded (${data.current_length?.toLocaleString()} / ${data.max_length?.toLocaleString()} characters). Please start a new conversation.`
    )
  )

  addProgressStepFromEvent(taskId, 'context_too_long', 'failed', data as unknown as Record<string, unknown>)
}

function handleAsk(taskId: string, data: Record<string, unknown>): void {
  const store = useChatStore.getState()
  const question = (data.question as string) || 'The assistant has a question for you.'

  store.addMessage(taskId, createMessage('assistant', question))
  addProgressStepFromEvent(taskId, 'ask', 'active', data)
}

function handleNotice(taskId: string, data: Record<string, unknown>): void {
  const store = useChatStore.getState()
  const message = (data.notice as string) || (data.message as string) || ''
  const progress = data.progress as number | undefined

  if (message) {
    // Check if this is a compacting notice
    const isCompacting =
      message.toLowerCase().includes('compact') ||
      message.toLowerCase().includes('summariz')

    if (isCompacting) {
      // Set notice state for the compacting UI (shown inline, no message bubble)
      store.setNotice(taskId, {
        message,
        type: 'compacting',
        progress,
      })
    } else {
      // Regular notice - add as system message
      store.addMessage(taskId, createMessage('system', message))
    }
  }
}

/**
 * Clear notice when compacting is done
 * Called when we receive end or other events that indicate compacting is complete
 */
function clearCompactingNotice(taskId: string): void {
  const store = useChatStore.getState()
  const task = store.getTask(taskId)
  if (task?.notice?.type === 'compacting') {
    store.setNotice(taskId, null)
  }
}

// ============ Main Connection Function ============

/**
 * Start an SSE connection to the orchestrator
 */
export async function startSSEConnection(options: SSEConnectionOptions): Promise<void> {
  const { projectId, taskId, question, searchEnabled, agents, attachments, onOpen, onError, onClose } = options

  const store = useChatStore.getState()
  const { accessToken } = useAuthStore.getState()

  // Create abort controller for this connection
  const abortController = new AbortController()
  setSSEController(taskId, abortController)

  // Set connecting state
  store.setConnecting(true)

  const requestBody: StartChatRequest = {
    project_id: projectId,
    task_id: taskId,
    question,
    language: navigator.language,
    ...(searchEnabled !== undefined && { search_enabled: searchEnabled }),
    ...(agents && { agents }),
    ...(attachments && { attachments }),
  }

  try {
    await fetchEventSource(`${ORCHESTRATOR_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify(requestBody),
      signal: abortController.signal,
      openWhenHidden: true, // Keep connection open when tab is hidden

      async onopen(response) {
        store.setConnecting(false)

        if (response.ok) {
          console.log('[SSE] Connection opened')
          store.setTaskStatus(taskId, 'running')
          onOpen?.()
        } else {
          const errorText = await response.text()
          throw new Error(`SSE connection failed: ${response.status} ${errorText}`)
        }
      },

      onmessage(event) {
        if (!event.data) return

        try {
          const sseEvent: SSEEvent = JSON.parse(event.data)
          handleSSEEvent(taskId, sseEvent)
        } catch (error) {
          console.error('[SSE] Failed to parse event:', error, event.data)
        }
      },

      onerror(error) {
        console.error('[SSE] Error:', error)
        store.setConnecting(false)

        // Check if this is a retryable error
        if (
          error instanceof TypeError ||
          (error as Error)?.message?.includes('Failed to fetch') ||
          (error as Error)?.message?.includes('NetworkError')
        ) {
          console.warn('[SSE] Connection error, will retry...')
          // Let fetchEventSource handle retry
          return
        }

        // For other errors, cleanup and notify
        removeSSEController(taskId)
        store.setTaskError(taskId, (error as Error)?.message || 'Connection error')
        onError?.(error as Error)

        // Throw to stop retrying
        throw error
      },

      onclose() {
        console.log('[SSE] Connection closed')
        store.setConnecting(false)
        removeSSEController(taskId)
        onClose?.()
      },
    })
  } catch (error) {
    console.error('[SSE] Connection error:', error)
    store.setConnecting(false)
    removeSSEController(taskId)

    if ((error as Error)?.name !== 'AbortError') {
      store.setTaskError(taskId, (error as Error)?.message || 'Failed to connect')
      onError?.(error as Error)
    }
  }
}

/**
 * Stop an active SSE connection
 */
export function stopSSEConnection(taskId: string): void {
  removeSSEController(taskId)
  useChatStore.getState().stopTask(taskId)
}

/**
 * Send a follow-up message (improve) to an existing conversation
 */
export async function sendImproveMessage(
  projectId: string,
  question: string,
  taskId?: string,
  options?: {
    searchEnabled?: boolean
    agents?: Array<{ name: string; tools: string[] }>
    attachments?: ImproveChatRequest['attachments']
  }
): Promise<void> {
  const { accessToken } = useAuthStore.getState()

  try {
    const response = await fetch(`${ORCHESTRATOR_URL}/chat/${projectId}/improve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({
        question,
        task_id: taskId,
        ...(options?.searchEnabled !== undefined && { search_enabled: options.searchEnabled }),
        ...(options?.agents && { agents: options.agents }),
        ...(options?.attachments && { attachments: options.attachments }),
      }),
    })

    if (!response.ok) {
      throw new Error(`Failed to send message: ${response.status}`)
    }
  } catch (error) {
    console.error('[SSE] Improve error:', error)
    throw error
  }
}
