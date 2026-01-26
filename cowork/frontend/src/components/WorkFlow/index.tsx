/**
 * WorkFlow Component
 * 
 * Visualizes the multi-agent workflow as a horizontal layer of glass cards.
 * Agents appear, breathe while active, and fade to muted when done.
 * 
 * Design philosophy:
 * - Motion communicates state
 * - Glassmorphism creates depth
 * - Minimal text, maximum clarity
 */

import { useRef, useEffect, useMemo } from 'react'
import { cn } from '@/lib/utils'
import { Sparkles, AlertCircle } from 'lucide-react'
import type { WorkFlowProps } from './types'
import { AgentCard } from './AgentCard'

export function WorkFlow({
  agents,
  tasks: _tasks,
  activeAgentId,
  decomposeText,
  status,
  onAgentSelect,
  onTaskSelect: _onTaskSelect,
  className,
}: WorkFlowProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  
  // Sort agents: active first, then by creation time
  const sortedAgents = useMemo(() => {
    return [...agents].sort((a, b) => {
      // Active agent always first
      if (a.id === activeAgentId) return -1
      if (b.id === activeAgentId) return 1
      // Then by status: active > idle > done
      const statusOrder = { active: 0, idle: 1, done: 2 }
      const aOrder = statusOrder[a.status] ?? 1
      const bOrder = statusOrder[b.status] ?? 1
      if (aOrder !== bOrder) return aOrder - bOrder
      // Finally by activation time (newer first)
      return (b.activatedAt ?? 0) - (a.activatedAt ?? 0)
    })
  }, [agents, activeAgentId])

  // Auto-scroll to active agent
  useEffect(() => {
    if (activeAgentId && containerRef.current) {
      const activeElement = containerRef.current.querySelector(
        `[data-agent-id="${activeAgentId}"]`
      )
      if (activeElement) {
        activeElement.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'nearest', 
          inline: 'center' 
        })
      }
    }
  }, [activeAgentId])

  return (
    <div className={cn(
      'relative flex flex-col h-full overflow-hidden',
      // Theme-aware background with subtle gradient
      'bg-gradient-to-br from-[hsl(var(--workflow-bg))] to-[hsl(var(--workflow-surface))]',
      className
    )}>
      
      {/* ===== Header ===== */}
      <div className="flex-shrink-0 px-6 pt-5 pb-4">
        <WorkflowHeader status={status} agentCount={agents.length} />
      </div>
      
      {/* ===== Decomposition phase ===== */}
      {status === 'decomposing' && decomposeText && (
        <DecomposeAnimation text={decomposeText} />
      )}
      
      {/* ===== Agent Cards Grid ===== */}
      <div 
        ref={containerRef}
        className={cn(
          'flex-1 overflow-auto',
          'px-6 pb-6',
          // Smooth scrolling
          'scroll-smooth scrollbar-hide'
        )}
      >
        {status === 'idle' ? (
          <EmptyState />
        ) : (
          <div className={cn(
            // Horizontal scroll container with wrap fallback
            'flex flex-wrap gap-4',
            // On larger screens, single row with horizontal scroll
            'lg:flex-nowrap lg:overflow-x-auto lg:pb-4'
          )}>
            {sortedAgents.map((agent, index) => (
              <div
                key={agent.id}
                data-agent-id={agent.id}
                className={cn(
                  // Staggered entrance animation
                  'animate-slide-up',
                )}
                style={{ 
                  animationDelay: `${index * 75}ms`,
                  animationFillMode: 'both'
                }}
              >
                <AgentCard
                  agent={agent}
                  isActive={agent.id === activeAgentId}
                  isMuted={agent.status === 'done' && agent.id !== activeAgentId}
                  onSelect={() => onAgentSelect?.(agent.id)}
                />
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* ===== Error state overlay ===== */}
      {status === 'error' && (
        <ErrorOverlay />
      )}
      
      {/* ===== Completion state ===== */}
      {status === 'done' && agents.length > 0 && (
        <CompletionBanner agentCount={agents.length} />
      )}
    </div>
  )
}

/**
 * Workflow header with status indicator
 */
function WorkflowHeader({ 
  status, 
  agentCount 
}: { 
  status: WorkFlowProps['status']
  agentCount: number 
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-medium text-foreground">
          Workflow
        </h2>
        
        {/* Status badge */}
        {status !== 'idle' && (
          <span className={cn(
            'px-2.5 py-1 rounded-lg text-xs font-medium',
            'transition-all duration-300',
            status === 'decomposing' && 'bg-burnt-light text-burnt',
            status === 'running' && 'bg-[hsl(var(--status-active)/0.15)] text-[hsl(var(--status-active))]',
            status === 'done' && 'bg-[hsl(var(--status-done)/0.15)] text-[hsl(var(--status-done))]',
            status === 'error' && 'bg-destructive/15 text-destructive',
          )}>
            {status === 'decomposing' && 'Analyzing'}
            {status === 'running' && `${agentCount} agent${agentCount !== 1 ? 's' : ''} working`}
            {status === 'done' && 'Complete'}
            {status === 'error' && 'Error'}
          </span>
        )}
      </div>
    </div>
  )
}

/**
 * Animated decomposition text display
 */
function DecomposeAnimation({ text }: { text: string }) {
  return (
    <div className="px-6 pb-4">
      <div className={cn(
        'glass-subtle rounded-xl p-4',
        'max-h-32 overflow-y-auto'
      )}>
        <div className="flex items-start gap-3">
          <Sparkles className="w-4 h-4 text-burnt flex-shrink-0 mt-0.5 animate-pulse" />
          <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
            {text}
            <span className="inline-block w-1.5 h-4 bg-burnt animate-pulse ml-0.5 align-middle" />
          </p>
        </div>
      </div>
    </div>
  )
}

/**
 * Empty state when no workflow is active
 */
function EmptyState() {
  return (
    <div className="flex-1 flex items-center justify-center min-h-[200px]">
      <div className="text-center max-w-sm">
        <div className={cn(
          'w-16 h-16 mx-auto mb-4 rounded-2xl',
          'bg-muted/30 flex items-center justify-center'
        )}>
          <Sparkles className="w-8 h-8 text-muted-foreground/40" />
        </div>
        <h3 className="text-lg font-medium text-muted-foreground mb-2">
          No active workflow
        </h3>
        <p className="text-sm text-muted-foreground/60">
          Start a task in the chat to see agents spring into action
        </p>
      </div>
    </div>
  )
}

/**
 * Error state overlay
 */
function ErrorOverlay() {
  return (
    <div className={cn(
      'absolute inset-x-0 bottom-0',
      'bg-gradient-to-t from-destructive/10 to-transparent',
      'p-6 pt-12'
    )}>
      <div className={cn(
        'glass rounded-xl p-4',
        'border-destructive/30 border',
        'flex items-center gap-3'
      )}>
        <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0" />
        <p className="text-sm text-foreground">
          Something went wrong. Check the chat for details.
        </p>
      </div>
    </div>
  )
}

/**
 * Completion banner
 */
function CompletionBanner({ agentCount }: { agentCount: number }) {
  return (
    <div className={cn(
      'absolute inset-x-0 bottom-0',
      'bg-gradient-to-t from-[hsl(var(--status-done)/0.05)] to-transparent',
      'p-6 pt-12 pointer-events-none'
    )}>
      <div className={cn(
        'glass-subtle rounded-xl p-3',
        'flex items-center justify-center gap-2',
        'text-sm text-[hsl(var(--status-done))]'
      )}>
        <span>✓</span>
        <span>
          Task completed by {agentCount} agent{agentCount !== 1 ? 's' : ''}
        </span>
      </div>
    </div>
  )
}

// Re-export types and subcomponents
export * from './types'
export { AgentCard } from './AgentCard'
export { TaskPill } from './TaskPill'
export { ToolkitActivity, ToolkitActivityList } from './ToolkitActivity'
export { WorkFlowPanel } from './WorkFlowPanel'

export default WorkFlow

