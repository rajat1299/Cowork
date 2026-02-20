import { orchestratorApi, ORCHESTRATOR_URL } from './client'

// ============ Types ============

export interface StartChatRequest {
  project_id: string
  task_id: string
  question: string
  // Phase 5 additions (optional for now)
  model_provider?: string
  model_type?: string
  api_key?: string
}

export interface ImproveRequest {
  question: string
}

export interface UploadedFileInfo {
  id: string
  name: string
  content_type?: string
  size: number
  path: string
  relative_path: string
  url: string
}

export interface UploadResponse {
  files: UploadedFileInfo[]
}

export interface SSEEvent {
  task_id: string
  step: string
  data: Record<string, unknown>
  timestamp: number
}

// Known step types from backend
export type StepType =
  | 'confirmed'
  | 'decompose_text'
  | 'to_sub_tasks'
  | 'activate_agent'
  | 'deactivate_agent'
  | 'activate_toolkit'
  | 'deactivate_toolkit'
  | 'task_state'
  | 'streaming'
  | 'artifact'
  | 'end'
  | 'error'

// ============ Chat Endpoints ============

export const chat = {
  /**
   * Start a new chat task. Returns immediately - actual responses come via SSE.
   * Use `createSSEConnection` to listen for events.
   */
  start: (data: StartChatRequest): Promise<void> =>
    orchestratorApi.post('/chat', data),

  /**
   * Send a follow-up question to an existing task
   */
  improve: (projectId: string, data: ImproveRequest): Promise<void> =>
    orchestratorApi.post(`/chat/${projectId}/improve`, data),

  /**
   * Stop a running task
   */
  stop: (projectId: string): Promise<void> =>
    orchestratorApi.delete(`/chat/${projectId}`),
}

export const files = {
  upload: (formData: FormData): Promise<UploadResponse> =>
    orchestratorApi.upload('/files/upload', formData),
}

// ============ SSE Connection ============

export interface SSEConnectionOptions {
  onEvent: (event: SSEEvent) => void
  onError?: (error: Event) => void
  onOpen?: () => void
}

/**
 * Create an SSE connection to the orchestrator for a chat task.
 * Returns an EventSource that can be closed when done.
 *
 * Note: This is a placeholder structure. Full SSE implementation
 * will be added when we wire up the chat flow.
 */
export function createSSEConnection(
  taskId: string,
  options: SSEConnectionOptions
): EventSource {
  // EventSource doesn't support custom headers. Use withCredentials
  // to send cookies for authentication instead of query params.
  const url = `${ORCHESTRATOR_URL}/chat/stream?task_id=${taskId}`
  const eventSource = new EventSource(url, { withCredentials: true })

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as SSEEvent
      options.onEvent(data)
    } catch (err) {
      console.error('Failed to parse SSE event:', err)
    }
  }

  eventSource.onerror = (error) => {
    options.onError?.(error)
  }

  eventSource.onopen = () => {
    options.onOpen?.()
  }

  return eventSource
}

/**
 * Alternative: Use fetch with ReadableStream for SSE with proper auth headers.
 * This is more robust than EventSource for authenticated endpoints.
 */
export async function createAuthenticatedSSEStream(
  request: StartChatRequest,
  options: SSEConnectionOptions
): Promise<AbortController> {
  const controller = new AbortController()

  try {
    const response = await fetch(`${ORCHESTRATOR_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(request),
      signal: controller.signal,
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    options.onOpen?.()

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('No response body')
    }

    // Read the stream
    const processStream = async () => {
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Process complete SSE messages
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6)) as SSEEvent
              options.onEvent(data)
            } catch (err) {
              console.error('Failed to parse SSE data:', err)
            }
          }
        }
      }
    }

    processStream().catch((err) => {
      if (err.name !== 'AbortError') {
        options.onError?.(err)
      }
    })
  } catch (err) {
    options.onError?.(err as Event)
  }

  return controller
}
