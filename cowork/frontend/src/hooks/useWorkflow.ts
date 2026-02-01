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

import { useMemo, useRef, useCallback, useEffect } from 'react'
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
import { generateId } from '@/types/chat'

/**
 * Hook to get workflow state from the active task
 */
export function useWorkflow() {
  // Use a stable selector instead of calling getActiveTask() which creates new references
  const task = useChatStore((s) => s.activeTaskId ? s.tasks[s.activeTaskId] : undefined)
  
  // Track toolkit activities keyed by agent_name (since that's what events provide)
  const toolkitActivitiesByNameRef = useRef<Map<string, ToolkitActivity[]>>(new Map())
  
  // Track agent_name -> agent_id mapping for correlation
  const agentNameToIdRef = useRef<Map<string, string>>(new Map())
  
  // Build agent name->id mapping from current agents (useEffect for side effects)
  useEffect(() => {
    if (!task?.activeAgents) return
    task.activeAgents.forEach((agent) => {
      agentNameToIdRef.current.set(agent.name, agent.id)
    })
  }, [task?.activeAgents])
  
  // Transform agents from store format to workflow format
  const agents = useMemo<WorkflowAgent[]>(() => {
    if (!task?.activeAgents) return []
    
    return task.activeAgents.map((agent) => {
      // Get toolkit activities for this agent (by name, since events use name)
      const activities = toolkitActivitiesByNameRef.current.get(agent.name) || []
      
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
  
  /**
   * Add toolkit activity - keyed by agent_name since that's what events provide
   */
  const addToolkitActivity = useCallback((
    agentName: string,
    processTaskId: string,
    toolkitName: string,
    methodName: string,
    message: string
  ) => {
    const existing = toolkitActivitiesByNameRef.current.get(agentName) || []
    const newActivity: ToolkitActivity = {
      id: generateId(),
      agentName,
      processTaskId,
      toolkitName,
      methodName,
      message,
      status: 'running',
      timestamp: Date.now(),
    }
    toolkitActivitiesByNameRef.current.set(agentName, [...existing, newActivity])
  }, [])
  
  /**
   * Update toolkit activity status (on deactivate_toolkit)
   */
  const completeToolkitActivity = useCallback((
    agentName: string,
    processTaskId: string,
    toolkitName: string,
    methodName: string,
    output?: string
  ) => {
    const existing = toolkitActivitiesByNameRef.current.get(agentName) || []
    const updated = existing.map((a) => {
      // Match by task, toolkit, method, and running status
      if (
        a.processTaskId === processTaskId &&
        a.toolkitName === toolkitName &&
        a.methodName === methodName &&
        a.status === 'running'
      ) {
        return { ...a, status: 'done' as const, message: output || a.message }
      }
      return a
    })
    toolkitActivitiesByNameRef.current.set(agentName, updated)
  }, [])
  
  /**
   * Get agent_id from agent_name (for correlation)
   */
  const getAgentIdByName = useCallback((agentName: string): string | undefined => {
    return agentNameToIdRef.current.get(agentName)
  }, [])
  
  /**
   * Clear toolkit activities (e.g., on new task)
   */
  const clearToolkitActivities = useCallback(() => {
    toolkitActivitiesByNameRef.current.clear()
    agentNameToIdRef.current.clear()
  }, [])
  
  return {
    // Workflow state (for WorkFlow component)
    agents,
    tasks,
    activeAgentId,
    decomposeText: task?.streamingDecomposeText ?? '',
    status,
    
    // Toolkit activity management (for SSE handler)
    addToolkitActivity,
    completeToolkitActivity,
    getAgentIdByName,
    clearToolkitActivities,
    
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

