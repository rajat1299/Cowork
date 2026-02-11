import type { ProgressStep, StepType, TaskInfo } from '../types/chat'

export type CheckpointStatus = 'pending' | 'active' | 'completed' | 'failed'

export interface TurnCheckpoint {
  id: string
  label: string
  fullLabel?: string
  status: CheckpointStatus
}

export interface SearchEvidenceResult {
  title: string
  url?: string
  domain?: string
  error?: string
}

export interface EvidenceBlock {
  id: string
  timestamp: number
  summary: string
  status: 'running' | 'done' | 'error'
  toolkit?: string
  method?: string
  request?: string
  result?: string
  filePath?: string
  searchResults?: SearchEvidenceResult[]
}

export interface TurnExecutionView {
  turnSteps: ProgressStep[]
  subtasks: TaskInfo[]
  checkpoints: TurnCheckpoint[]
  evidence: EvidenceBlock[]
  connectors: string[]
  skills: string[]
}

const SECRET_KEY_PATTERN = /(token|api[_-]?key|secret|password|authorization|cookie|bearer)/i
const MAX_CONDENSED_LABEL_CHARS = 165

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function parseMaybeJson(value: string): unknown {
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

function truncateText(value: string, max = 1200): string {
  if (value.length <= max) return value
  return `${value.slice(0, max)}... (truncated)`
}

function redactDeep(value: unknown, keyHint = ''): unknown {
  if (typeof value === 'string') {
    if (SECRET_KEY_PATTERN.test(keyHint)) return '[REDACTED]'
    return truncateText(value)
  }
  if (Array.isArray(value)) {
    return value.map((item) => redactDeep(item, keyHint))
  }
  if (isRecord(value)) {
    const output: Record<string, unknown> = {}
    Object.entries(value).forEach(([key, item]) => {
      if (SECRET_KEY_PATTERN.test(key)) {
        output[key] = '[REDACTED]'
      } else {
        output[key] = redactDeep(item, key)
      }
    })
    return output
  }
  return value
}

function formatStructured(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return truncateText(value)
  try {
    return truncateText(JSON.stringify(redactDeep(value), null, 2))
  } catch {
    return truncateText(String(value))
  }
}

function normalizeTaskStatus(raw: unknown): TaskInfo['status'] {
  const value = typeof raw === 'string' ? raw.toLowerCase() : ''
  if (value === 'running' || value === 'processing') return 'running'
  if (value === 'done' || value === 'completed') return 'completed'
  if (value === 'failed') return 'failed'
  if (value === 'paused') return 'paused'
  return 'pending'
}

function normalizeWhitespace(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function clipAtNaturalBoundary(value: string, max: number): string {
  if (value.length <= max) return value
  const candidate = value.slice(0, max)
  const boundary = Math.max(
    candidate.lastIndexOf('. '),
    candidate.lastIndexOf('; '),
    candidate.lastIndexOf(': '),
    candidate.lastIndexOf(', ')
  )
  if (boundary > Math.floor(max * 0.55)) {
    return candidate.slice(0, boundary).trim()
  }
  return candidate.trim()
}

function findDeliverableFilename(value: string): string | undefined {
  const fileRegex = /([A-Za-z0-9 _-]+\.(?:md|txt|csv|json|pdf|docx|pptx|xlsx))/gi
  const matches = [...value.matchAll(fileRegex)]
  if (matches.length === 0) return undefined
  return matches[matches.length - 1]?.[1]
}

function condenseCheckpointLabel(fullText: string): string {
  const normalized = normalizeWhitespace(fullText)
  if (!normalized) return 'Subtask'

  const firstSentence = normalized.split(/(?<=[.?!])\s+/)[0] || normalized
  let condensed = firstSentence
    .replace(/^(please|kindly)\s+/i, '')
    .replace(/\bthe document must include sections on:.*$/i, '')
    .replace(/\bto ensure it maintains.*$/i, '')
    .trim()

  const filename = findDeliverableFilename(normalized)
  if (filename && !condensed.toLowerCase().includes(filename.toLowerCase())) {
    condensed = `${condensed} -> ${filename}`
  }

  condensed = clipAtNaturalBoundary(condensed, MAX_CONDENSED_LABEL_CHARS)
  if (condensed.length < normalized.length) {
    condensed = `${condensed}...`
  }
  return condensed || 'Subtask'
}

function normalizeToolName(raw: unknown): string {
  if (typeof raw !== 'string') return ''
  return raw.replace(/toolkitwithevents$/i, '').replace(/toolkit$/i, '').trim()
}

function summarizeToolkitAction(toolkit: string, method: string, resultText: string): string {
  const toolkitKey = toolkit.toLowerCase()
  const methodKey = method.toLowerCase()
  if (toolkitKey.includes('search')) return 'Searched the web'
  if (toolkitKey.includes('file') && /written to file|stored tool output|created/i.test(resultText)) {
    return 'Created a file'
  }
  if (toolkitKey.includes('terminal') || methodKey.includes('shell') || methodKey.includes('command')) {
    return 'Ran a command'
  }
  if (methodKey.includes('todo')) return 'Updated todo list'
  return `Ran ${method || toolkit || 'tool'}`
}

function domainFromUrl(url?: string): string | undefined {
  if (!url) return undefined
  try {
    return new URL(url).hostname
  } catch {
    return undefined
  }
}

function extractSearchResults(resultText: string): SearchEvidenceResult[] | undefined {
  const parsed = parseMaybeJson(resultText)
  if (!isRecord(parsed)) return undefined
  if (!Array.isArray(parsed.results)) return undefined
  return parsed.results
    .filter((item) => isRecord(item))
    .map((item) => {
      const title = typeof item.title === 'string'
        ? item.title
        : typeof item.text === 'string'
        ? item.text
        : typeof item.url === 'string'
        ? item.url
        : 'Search result'
      const url = typeof item.url === 'string' ? item.url : undefined
      const error = typeof item.error === 'string' ? item.error : undefined
      return {
        title,
        url,
        domain: domainFromUrl(url),
        error,
      }
    })
}

function findLatestTurnSteps(progressSteps: ProgressStep[]): ProgressStep[] {
  let startIndex = -1
  for (let i = progressSteps.length - 1; i >= 0; i -= 1) {
    if (progressSteps[i].step === 'confirmed') {
      startIndex = i
      break
    }
  }
  if (startIndex === -1) return progressSteps
  return progressSteps.slice(startIndex)
}

function deriveSubtasks(turnSteps: ProgressStep[]): TaskInfo[] {
  const latestSubtaskStep = [...turnSteps].reverse().find((step) => step.step === 'to_sub_tasks')
  const subtasks: TaskInfo[] = []
  if (latestSubtaskStep?.data && Array.isArray(latestSubtaskStep.data.sub_tasks)) {
    latestSubtaskStep.data.sub_tasks.forEach((raw, index) => {
      if (!isRecord(raw)) return
      const id = typeof raw.id === 'string' ? raw.id : `step-${index + 1}`
      const title = typeof raw.content === 'string'
        ? raw.content
        : typeof raw.title === 'string'
        ? raw.title
        : `Step ${index + 1}`
      subtasks.push({
        id,
        title,
        status: normalizeTaskStatus(raw.state ?? raw.status),
      })
    })
  }

  const indexById = new Map<string, number>()
  subtasks.forEach((task, index) => indexById.set(task.id, index))

  turnSteps.forEach((step) => {
    const data = step.data || {}
    if (step.step === 'assign_task') {
      const taskId = typeof data.task_id === 'string' ? data.task_id : ''
      const index = indexById.get(taskId)
      if (index === undefined) return
      subtasks[index] = {
        ...subtasks[index],
        status: normalizeTaskStatus(data.state),
      }
    }
    if (step.step === 'task_state') {
      const taskId = typeof data.task_id === 'string' ? data.task_id : ''
      const index = indexById.get(taskId)
      if (index === undefined) return
      subtasks[index] = {
        ...subtasks[index],
        status: normalizeTaskStatus(data.state),
      }
    }
  })

  return subtasks
}

function deriveGenericCheckpoints(turnSteps: ProgressStep[]): TurnCheckpoint[] {
  const hasConfirmed = turnSteps.some((step) => step.step === 'confirmed')
  const hasExecution = turnSteps.some((step) =>
    step.step === 'assign_task' ||
    step.step === 'activate_toolkit' ||
    step.step === 'activate_agent' ||
    step.step === 'create_agent' ||
    step.step === 'streaming'
  )
  const hasEnd = turnSteps.some((step) => step.step === 'end')
  const hasError = turnSteps.some((step) => step.step === 'error' || step.step === 'context_too_long')

  const analyzeStatus: CheckpointStatus =
    hasExecution || hasEnd || hasError ? 'completed' : hasConfirmed ? 'active' : 'pending'
  const executeStatus: CheckpointStatus =
    hasError ? 'failed' : hasEnd ? 'completed' : hasExecution ? 'active' : 'pending'
  const finalizeStatus: CheckpointStatus =
    hasError ? 'failed' : hasEnd ? 'completed' : hasExecution ? 'active' : 'pending'

  return [
    { id: 'analyze', label: 'Analyze request', status: analyzeStatus },
    { id: 'execute', label: 'Execute plan', status: executeStatus },
    { id: 'finalize', label: 'Finalize output', status: finalizeStatus },
  ]
}

function deriveCheckpoints(turnSteps: ProgressStep[], subtasks: TaskInfo[]): TurnCheckpoint[] {
  if (subtasks.length === 0) return deriveGenericCheckpoints(turnSteps)
  return subtasks.map((task) => ({
    id: task.id,
    label: condenseCheckpointLabel(task.title),
    fullLabel: normalizeWhitespace(task.title),
    status:
      task.status === 'completed'
        ? 'completed'
        : task.status === 'failed'
        ? 'failed'
        : task.status === 'running'
        ? 'active'
        : 'pending',
  }))
}

function deriveEvidence(turnSteps: ProgressStep[]): EvidenceBlock[] {
  const evidence: EvidenceBlock[] = []
  const activeByKey = new Map<string, EvidenceBlock>()

  turnSteps.forEach((step, index) => {
    if (step.step !== 'activate_toolkit' && step.step !== 'deactivate_toolkit') {
      return
    }
    const data = step.data || {}
    const toolkit = normalizeToolName(data.toolkit || data.toolkit_name)
    const method = typeof data.method === 'string'
      ? data.method
      : typeof data.method_name === 'string'
      ? data.method_name
      : 'tool'
    const agent = typeof data.agent === 'string'
      ? data.agent
      : typeof data.agent_name === 'string'
      ? data.agent_name
      : ''
    const processTaskId = typeof data.process_task_id === 'string' ? data.process_task_id : ''
    const key = `${agent}|${processTaskId}|${toolkit}|${method}`
    const requestText = formatStructured(data.message)
    const resultText = formatStructured(data.result ?? data.message)
    const searchResults = toolkit.toLowerCase().includes('search')
      ? extractSearchResults(String(data.result ?? data.message ?? ''))
      : undefined

    if (step.step === 'activate_toolkit') {
      const block: EvidenceBlock = {
        id: `evidence-${step.timestamp ?? index}`,
        timestamp: step.timestamp ?? index,
        summary: summarizeToolkitAction(toolkit, method, ''),
        status: 'running',
        toolkit,
        method,
        request: requestText || undefined,
      }
      evidence.push(block)
      activeByKey.set(key, block)
      return
    }

    const active = activeByKey.get(key)
    const nextSummary = summarizeToolkitAction(toolkit, method, resultText)
    if (active) {
      active.status = /error|failed|exception/i.test(resultText) ? 'error' : 'done'
      active.summary = nextSummary
      active.result = resultText || undefined
      active.searchResults = searchResults
      const fileMatch = resultText.match(/(?:written to file|artifact):\s*([^\n]+)/i)
      if (fileMatch) active.filePath = fileMatch[1]?.trim()
      activeByKey.delete(key)
      return
    }

    evidence.push({
      id: `evidence-${step.timestamp ?? index}`,
      timestamp: step.timestamp ?? index,
      summary: nextSummary,
      status: /error|failed|exception/i.test(resultText) ? 'error' : 'done',
      toolkit,
      method,
      result: resultText || undefined,
      searchResults,
    })
  })

  return evidence
}

function deriveContextSignals(turnSteps: ProgressStep[]): { connectors: string[]; skills: string[] } {
  const connectors = new Set<string>()
  const skills = new Set<string>()

  turnSteps.forEach((step) => {
    const data = step.data || {}
    if (step.step === 'activate_toolkit' || step.step === 'deactivate_toolkit') {
      const toolkit = normalizeToolName(data.toolkit || data.toolkit_name).toLowerCase()
      if (!toolkit) return
      if (toolkit.includes('search')) connectors.add('Web search')
      else if (toolkit.includes('file')) connectors.add('Files')
      else if (toolkit.includes('terminal')) connectors.add('Terminal')
      else if (toolkit.includes('browser')) connectors.add('Browser')
      else connectors.add(toolkit)
    }
    if (step.step === 'create_agent' && Array.isArray(data.tools)) {
      ;(data.tools as unknown[]).forEach((tool) => {
        if (typeof tool === 'string' && tool.trim()) {
          skills.add(tool.replace(/_/g, ' '))
        }
      })
    }
    if (typeof data.skill_id === 'string' && data.skill_id.trim()) {
      skills.add(data.skill_id.replace(/_/g, ' '))
    }
  })

  return {
    connectors: [...connectors],
    skills: [...skills],
  }
}

export function buildTurnExecutionView(progressSteps: ProgressStep[]): TurnExecutionView {
  const turnSteps = findLatestTurnSteps(progressSteps)
  const subtasks = deriveSubtasks(turnSteps)
  const checkpoints = deriveCheckpoints(turnSteps, subtasks)
  const evidence = deriveEvidence(turnSteps)
  const context = deriveContextSignals(turnSteps)
  return {
    turnSteps,
    subtasks,
    checkpoints,
    evidence,
    connectors: context.connectors,
    skills: context.skills,
  }
}

export function mapBackendStepToProgressStep(step: {
  step: string
  data?: Record<string, unknown>
  timestamp?: number
}): ProgressStep {
  return {
    step: step.step as StepType,
    label: step.step,
    status: 'completed',
    timestamp: step.timestamp ?? Date.now(),
    data: step.data || {},
  }
}
