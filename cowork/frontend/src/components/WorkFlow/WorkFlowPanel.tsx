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

import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { ChevronDown, ChevronUp } from 'lucide-react'
import type { WorkFlowProps } from './types'
import { AgentCard } from './AgentCard'
import { getAgentDisplayName, getAgentAccentClass } from './types'

interface WorkFlowPanelProps extends WorkFlowProps {
  /** Whether the panel should be visible */
  isVisible: boolean
}

export function WorkFlowPanel({
  agents,
  tasks: _tasks,
  activeAgentId,
  decomposeText,
  status,
  onAgentSelect,
  isVisible,
  className,
}: WorkFlowPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  
  // Auto-expand when first agent is created, collapse when done
  useEffect(() => {
    if (status === 'running' && agents.length > 0 && !isExpanded) {
      setIsExpanded(true)
    }
    if (status === 'done' || status === 'idle') {
      setIsExpanded(false)
    }
  }, [status, agents.length])

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
                    name={agent.name}
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
            <div className="px-4 pb-4 pt-1">
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
  name: _name, 
  type, 
  isActive, 
  isDone 
}: { 
  name: string
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

