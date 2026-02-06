/**
 * useWorkflow Hook
 * 
 * Bridges the chatStore state to WorkFlow component props.
 * Transforms AgentInfo/TaskInfo to WorkflowAgent/WorkflowTask format.
 * 
 * Correlation strategy:
 * - Agents are keyed by agent_id (from create_agent)
 * - Tasks use assignee_id which maps to agent_id
 * - Toolkit events use agent_name (not agent_id), so we correlate by name
 */

import { useMemo } from 'react'
import { useChatStore } from '@/stores/chatStore'
import type { AgentInfo, TaskInfo, TaskStatus } from '@/types/chat'
import type { 
  WorkflowAgent, 
  WorkflowTask, 
  WorkflowState,
  ToolkitActivity,
  AgentStatus,
  AgentType,
  TaskState,
} from '@/components/WorkFlow/types'

/**
 * Hook to get workflow state from the active task
 */
export function useWorkflow() {
  // Use a stable selector instead of calling getActiveTask() which creates new references
  const task = useChatStore((s) => s.activeTaskId ? s.tasks[s.activeTaskId] : undefined)

  const toolkitActivitiesByName = useMemo(() => {
    const map = new Map<string, ToolkitActivity[]>()
    const runningIndex = new Map<string, ToolkitActivity>()
    const steps = task?.progressSteps || []

    steps.forEach((step, index) => {
      if (step.step !== 'activate_toolkit' && step.step !== 'deactivate_toolkit') {
        return
      }
      const data = step.data || {}
      const agentName = typeof data.agent === 'string' ? data.agent : 'agent'
      const toolkitName = typeof data.toolkit === 'string' ? data.toolkit : 'tool'
      const methodName = typeof data.method === 'string' ? data.method : 'tool'
      const processTaskId = typeof data.process_task_id === 'string' ? data.process_task_id : ''
      const message =
        typeof data.message === 'string'
          ? data.message
          : typeof data.result === 'string'
          ? data.result
          : ''
      const key = `${agentName}|${processTaskId}|${toolkitName}|${methodName}`

      if (step.step === 'activate_toolkit') {
        const activity: ToolkitActivity = {
          id: `${step.timestamp ?? index}-${key}`,
          agentName,
          processTaskId,
          toolkitName,
          methodName,
          message,
          status: 'running',
          timestamp: step.timestamp ?? Date.now(),
        }
        const existing = map.get(agentName) || []
        map.set(agentName, [...existing, activity])
        runningIndex.set(key, activity)
        return
      }

      const running = runningIndex.get(key)
      if (running) {
        running.status = 'done'
        if (message) {
          running.message = message
        }
        runningIndex.delete(key)
        return
      }

      const fallback: ToolkitActivity = {
        id: `${step.timestamp ?? index}-${key}`,
        agentName,
        processTaskId,
        toolkitName,
        methodName,
        message,
        status: 'done',
        timestamp: step.timestamp ?? Date.now(),
      }
      const existing = map.get(agentName) || []
      map.set(agentName, [...existing, fallback])
    })

    return map
  }, [task?.progressSteps])
  
  // Transform agents from store format to workflow format
  const agents = useMemo<WorkflowAgent[]>(() => {
    if (!task?.activeAgents) return []
    
    return task.activeAgents.map((agent) => {
      const activities = toolkitActivitiesByName.get(agent.name) || []
      
      return {
        id: agent.id,
        name: agent.name,
        type: inferAgentType(agent.name),
        status: mapAgentStatus(agent.status),
        tools: agent.tools || [],  // From create_agent event
        tasks: agent.tasks.map(transformTask),
        toolkitActivity: activities,
        activatedAt: agent.status === 'active' ? Date.now() : undefined,
      }
    })
  }, [task?.activeAgents])
  
  // Get all subtasks (for summary view)
  const tasks = useMemo<WorkflowTask[]>(() => {
    if (!task?.subtasks) return []
    return task.subtasks.map(transformTask)
  }, [task?.subtasks])
  
  // Determine active agent (most recently activated)
  const activeAgentId = useMemo<string | null>(() => {
    if (!agents.length) return null
    
    // Find agent with 'active' status
    const activeAgent = agents.find((a) => a.status === 'active')
    return activeAgent?.id ?? null
  }, [agents])
  
  // Determine workflow status
  const status = useMemo<WorkflowState['status']>(() => {
    if (!task) return 'idle'
    if (task.error) return 'error'
    if (task.status === 'completed') return 'done'
    if (task.status === 'failed') return 'error'
    if (task.streamingDecomposeText) return 'decomposing'
    if (task.status === 'running') return 'running'
    return 'idle'
  }, [task?.status, task?.error, task?.streamingDecomposeText])
  
  return {
    // Workflow state (for WorkFlow component)
    agents,
    tasks,
    activeAgentId,
    decomposeText: task?.streamingDecomposeText ?? '',
    status,

    // Raw task reference
    task,
  }
}

// ============ Helper Functions ============

/**
 * Infer agent type from name (for icon/color selection)
 */
function inferAgentType(name: string): AgentType {
  const normalized = name.toLowerCase()
  
  if (normalized.includes('developer') || normalized.includes('code')) {
    return 'developer_agent'
  }
  if (normalized.includes('search') || normalized.includes('web')) {
    return 'search_agent'
  }
  if (normalized.includes('document') || normalized.includes('doc') || normalized.includes('file')) {
    return 'document_agent'
  }
  if (normalized.includes('multi') || normalized.includes('modal') || normalized.includes('image') || normalized.includes('video')) {
    return 'multi_modal_agent'
  }
  
  return name // Custom agent keeps its name as type
}

/**
 * Map store agent status to workflow status
 */
function mapAgentStatus(status: AgentInfo['status']): AgentStatus {
  switch (status) {
    case 'active': return 'active'
    case 'finished': return 'done'
    case 'idle': 
    default: return 'idle'
  }
}

/**
 * Transform TaskInfo to WorkflowTask
 */
function transformTask(task: TaskInfo): WorkflowTask {
  return {
    id: task.id,
    content: task.title,
    state: mapTaskStatus(task.status),
    failureCount: task.failureCount ?? 0,
    assigneeId: task.assignee,
  }
}

/**
 * Map TaskStatus to TaskState
 */
function mapTaskStatus(status: TaskStatus): TaskState {
  switch (status) {
    case 'running': return 'running'
    case 'completed': return 'completed'
    case 'failed': return 'failed'
    case 'pending':
    case 'paused':
    default: return 'waiting'
  }
}

export default useWorkflow
