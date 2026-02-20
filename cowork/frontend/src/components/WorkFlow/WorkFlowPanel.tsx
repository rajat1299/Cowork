/**
 * WorkFlowPanel Component
 * 
 * A collapsible workflow panel that sits above the chat area.
 * Only renders when a task is running. Designed to feel unified
 * with the chat interface - same surface, subtle presence.
 * 
 * States:
 * - Hidden: No task running
 * - Compact: Single row of agent indicators (default when running)
 * - Expanded: Full agent cards with details
 */

import { useState, useMemo } from 'react'
import { cn } from '@/lib/utils'
import { ChevronDown, ChevronUp } from 'lucide-react'
import type { WorkFlowProps } from './types'
import { AgentCard } from './AgentCard'
import { getAgentDisplayName, getAgentAccentClass } from './types'
import type { ProgressStep } from '@/types/chat'
import { getStepLabel } from '@/types/chat'

interface WorkFlowPanelProps extends WorkFlowProps {
  /** Whether the panel should be visible */
  isVisible: boolean
  timeline?: ProgressStep[]
}

export function WorkFlowPanel({
  agents,
  activeAgentId,
  decomposeText,
  status,
  onAgentSelect,
  isVisible,
  timeline,
  className,
}: WorkFlowPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const timelineItems = useMemo(() => {
    if (!timeline?.length) return []
    const filtered = timeline.filter((step) => step.step !== 'streaming' && step.step !== 'decompose_text')
    const recent = filtered.slice(-12).reverse()
    return recent.map((step, index) => ({
      id: `${step.timestamp ?? index}-${step.step}`,
      title: formatTimelineTitle(step),
      detail: formatTimelineDetail(step),
      status: step.status,
      time: formatTimelineTime(step.timestamp),
    }))
  }, [timeline])
  
  // Auto-expand when first agent is created, collapse when done
  const [prevStatus, setPrevStatus] = useState(status)
  if (prevStatus !== status) {
    setPrevStatus(status)
    if (status === 'running' && agents.length > 0) {
      setIsExpanded(true)
    }
    if (status === 'done' || status === 'idle') {
      setIsExpanded(false)
    }
  }

  // Don't render if not visible
  if (!isVisible || status === 'idle') {
    return null
  }

  return (
    <div
      className={cn(
        // Seamless integration with chat area - no heavy bg or borders
        'border-b border-border/20',
        // Smooth height animation
        'transition-all duration-500 ease-smooth overflow-hidden',
        className
      )}
    >
      {/* ===== Decomposition Phase ===== */}
      {status === 'decomposing' && decomposeText && (
        <DecomposeBar text={decomposeText} />
      )}

      {/* ===== Agents Bar ===== */}
      {agents.length > 0 && (
        <>
          {/* Compact Header (always visible when agents exist) */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className={cn(
              'w-full px-4 py-3 flex items-center justify-between',
              'hover:bg-muted/30 transition-colors duration-200',
              'focus:outline-none focus-visible:ring-1 focus-visible:ring-ring'
            )}
          >
            {/* Agent indicators */}
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Agents
              </span>
              
              <div className="flex items-center gap-1.5">
                {agents.map((agent) => (
                  <AgentDot
                    key={agent.id}
                    type={agent.type}
                    isActive={agent.id === activeAgentId}
                    isDone={agent.status === 'done'}
                  />
                ))}
              </div>
              
              {/* Status text */}
              <span className="text-xs text-muted-foreground">
                {getStatusText(agents, activeAgentId, status)}
              </span>
            </div>

            {/* Expand/collapse toggle */}
            <span className="text-muted-foreground/60">
              {isExpanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </span>
          </button>

          {/* Expanded Content */}
          <div
            className={cn(
              'overflow-hidden transition-all duration-400 ease-smooth',
              isExpanded ? 'max-h-[400px] opacity-100' : 'max-h-0 opacity-0'
            )}
          >
            <div className="px-4 pb-4 pt-1 space-y-4">
              <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide">
                {agents.map((agent, index) => (
                  <div
                    key={agent.id}
                    className="animate-fade-in flex-shrink-0"
                    style={{ animationDelay: `${index * 50}ms` }}
                  >
                    <AgentCard
                      agent={agent}
                      isActive={agent.id === activeAgentId}
                      isMuted={agent.status === 'done' && agent.id !== activeAgentId}
                      onSelect={() => onAgentSelect?.(agent.id)}
                      className="min-w-[260px] max-w-[280px]"
                    />
                  </div>
                ))}
              </div>

              {timelineItems.length > 0 && (
                <TimelineSection items={timelineItems} />
              )}
            </div>
          </div>
        </>
      )}

      {/* ===== Error indicator ===== */}
      {status === 'error' && (
        <div className="px-4 py-2 flex items-center justify-center gap-2 text-xs text-destructive">
          <span className="w-1.5 h-1.5 rounded-full bg-destructive" />
          <span>Something went wrong</span>
        </div>
      )}
    </div>
  )
}

/**
 * Compact agent indicator dot
 */
function AgentDot({
  type,
  isActive,
  isDone
}: {
  type: string
  isActive: boolean
  isDone: boolean
}) {
  const accentClass = getAgentAccentClass(type)
  const displayName = getAgentDisplayName(type)
  
  return (
    <div
      className={cn(
        'group relative',
        accentClass
      )}
      title={displayName}
    >
      {/* Dot */}
      <span
        className={cn(
          'block w-2.5 h-2.5 rounded-full transition-all duration-300',
          isActive && 'bg-[var(--agent-color)] scale-125',
          isDone && 'bg-muted-foreground/40',
          !isActive && !isDone && 'bg-muted-foreground/60'
        )}
      />
      
      {/* Active pulse ring */}
      {isActive && (
        <span className="absolute inset-0 rounded-full bg-[var(--agent-color)]/30 animate-ping" />
      )}
      
      {/* Tooltip */}
      <span className={cn(
        'absolute -bottom-6 left-1/2 -translate-x-1/2',
        'px-1.5 py-0.5 rounded text-[10px] whitespace-nowrap',
        'bg-popover text-popover-foreground shadow-sm',
        'opacity-0 group-hover:opacity-100 transition-opacity duration-200',
        'pointer-events-none'
      )}>
        {displayName}
      </span>
    </div>
  )
}

/**
 * Decomposition streaming bar
 */
function DecomposeBar({ text }: { text: string }) {
  // Show last ~100 chars for compact display
  const preview = text.length > 100 
    ? '...' + text.slice(-100) 
    : text

  return (
    <div className="px-4 py-3 border-b border-border/30">
      <div className="flex items-center gap-2">
        <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-burnt animate-pulse" />
        <p className="text-xs text-muted-foreground truncate">
          {preview}
        </p>
      </div>
    </div>
  )
}

function TimelineSection({ items }: { items: Array<{ id: string; title: string; detail?: string; status: string; time?: string }> }) {
  return (
    <div className="rounded-xl border border-border/30 bg-muted/10">
      <div className="flex items-center justify-between px-3 pt-3">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Event timeline
        </span>
      </div>
      <div className="px-3 pb-3 pt-2 space-y-2">
        {items.map((item) => (
          <div key={item.id} className="flex items-start gap-2">
            <span
              className={cn(
                'mt-1.5 h-2 w-2 rounded-full',
                item.status === 'active' && 'bg-[hsl(var(--status-active))]',
                item.status === 'completed' && 'bg-[hsl(var(--status-done))]',
                item.status === 'failed' && 'bg-destructive',
                item.status === 'pending' && 'bg-muted-foreground/40'
              )}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-xs text-foreground truncate">{item.title}</span>
                {item.time && (
                  <span className="text-[10px] text-muted-foreground">{item.time}</span>
                )}
              </div>
              {item.detail && (
                <div className="text-[11px] text-muted-foreground truncate">{item.detail}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function formatTimelineTitle(step: ProgressStep): string {
  if (step.step === 'activate_toolkit' || step.step === 'deactivate_toolkit') {
    const data = step.data || {}
    const toolkit = typeof data.toolkit === 'string' ? data.toolkit : ''
    const method = typeof data.method === 'string' ? data.method : ''
    const label = [toolkit, method].filter(Boolean).join(' · ')
    return label ? `Tool ${label}` : getStepLabel(step.step)
  }
  if (step.step === 'activate_agent' || step.step === 'deactivate_agent' || step.step === 'create_agent') {
    const data = step.data || {}
    const agent = typeof data.agent === 'string' ? data.agent : ''
    return agent ? `${getStepLabel(step.step)} · ${agent}` : getStepLabel(step.step)
  }
  if (step.step === 'assign_task') {
    const data = step.data || {}
    const content = typeof data.content === 'string' ? data.content : ''
    return content ? `Assign task · ${content}` : getStepLabel(step.step)
  }
  if (step.step === 'task_state') {
    const data = step.data || {}
    const state = typeof data.state === 'string' ? data.state : ''
    const content = typeof data.content === 'string' ? data.content : ''
    return content && state ? `${content} · ${state}` : getStepLabel(step.step)
  }
  if (step.step === 'artifact') {
    const data = step.data || {}
    const name = typeof data.name === 'string' ? data.name : ''
    return name ? `Artifact · ${name}` : getStepLabel(step.step)
  }
  return getStepLabel(step.step)
}

function formatTimelineDetail(step: ProgressStep): string | undefined {
  const data = step.data || {}
  if (step.step === 'activate_toolkit' || step.step === 'deactivate_toolkit') {
    const agent = typeof data.agent === 'string' ? data.agent : ''
    const message = typeof data.message === 'string' ? data.message : ''
    const result = typeof data.result === 'string' ? data.result : ''
    const detail = message || result
    return agent && detail ? `${agent} · ${detail}` : agent || detail || undefined
  }
  if (step.step === 'notice' || step.step === 'context_too_long') {
    const message = typeof data.message === 'string' ? data.message : ''
    return message || undefined
  }
  if (step.step === 'error') {
    const message = typeof data.message === 'string' ? data.message : ''
    return message || undefined
  }
  return undefined
}

function formatTimelineTime(timestamp?: number): string | undefined {
  if (!timestamp) return undefined
  return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/**
 * Get status text for header
 */
function getStatusText(
  agents: WorkFlowPanelProps['agents'],
  activeAgentId: string | null,
  status: WorkFlowPanelProps['status']
): string {
  if (status === 'decomposing') return 'Analyzing task...'
  if (status === 'done') return 'All done'
  if (status === 'error') return 'Error'
  
  const activeAgent = agents.find(a => a.id === activeAgentId)
  if (activeAgent) {
    const runningTasks = activeAgent.tasks.filter(t => 
      t.state === 'running'
    ).length
    if (runningTasks > 0) {
      return `${getAgentDisplayName(activeAgent.type)} working...`
    }
  }
  
  const workingCount = agents.filter(a => a.status === 'active').length
  if (workingCount > 0) {
    return `${workingCount} working`
  }
  
  return 'Starting...'
}

export default WorkFlowPanel
