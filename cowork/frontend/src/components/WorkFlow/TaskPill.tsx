/**
 * TaskPill Component
 * 
 * A minimal, elegant pill that represents a subtask.
 * Shows status through color and subtle animations.
 */

import { cn } from '@/lib/utils'
import { Check, Loader2, AlertCircle, Circle } from 'lucide-react'
import type { TaskPillProps, TaskState } from './types'
import { normalizeTaskState } from './types'

export function TaskPill({ task, onClick, className }: TaskPillProps) {
  const state = normalizeTaskState(task.state)
  
  // Truncate content for display
  const displayText = task.content.length > 60 
    ? task.content.slice(0, 57) + '...' 
    : task.content

  return (
    <button
      onClick={onClick}
      className={cn(
        // Base styles
        'group relative flex items-center gap-2 px-3 py-2 rounded-xl',
        'text-left text-sm transition-all duration-300 ease-smooth',
        'border border-transparent',
        
        // State-specific styles
        state === 'running' && [
          'bg-[hsl(var(--status-active)/0.1)]',
          'border-[hsl(var(--status-active)/0.3)]',
          'text-foreground',
        ],
        state === 'waiting' && [
          'bg-muted/50',
          'text-muted-foreground',
          'hover:bg-muted hover:text-foreground',
        ],
        state === 'completed' && [
          'bg-[hsl(var(--status-done)/0.08)]',
          'text-muted-foreground',
        ],
        state === 'failed' && [
          'bg-[hsl(var(--status-failed)/0.1)]',
          'border-[hsl(var(--status-failed)/0.3)]',
          'text-[hsl(var(--status-failed))]',
        ],
        
        // Hover effect
        'hover:scale-[1.02] active:scale-[0.98]',
        
        className
      )}
    >
      {/* Status icon */}
      <span className="flex-shrink-0">
        <StatusIcon state={state} />
      </span>
      
      {/* Task content */}
      <span className="flex-1 min-w-0 truncate">
        {displayText}
      </span>
      
      {/* Failure count badge */}
      {task.failureCount > 0 && state !== 'completed' && (
        <span className={cn(
          'flex-shrink-0 text-xs px-1.5 py-0.5 rounded-md',
          state === 'failed' 
            ? 'bg-[hsl(var(--status-failed)/0.2)] text-[hsl(var(--status-failed))]'
            : 'bg-muted text-muted-foreground'
        )}>
          ×{task.failureCount}
        </span>
      )}
    </button>
  )
}

function StatusIcon({ state }: { state: TaskState }) {
  const normalized = normalizeTaskState(state)
  
  switch (normalized) {
    case 'running':
      return (
        <span className="relative">
          <Loader2 className="w-4 h-4 animate-spin text-[hsl(var(--status-active))]" />
          {/* Pulse ring behind spinner */}
          <span className="absolute inset-0 rounded-full bg-[hsl(var(--status-active)/0.3)] animate-pulse-ring" />
        </span>
      )
    case 'completed':
      return <Check className="w-4 h-4 text-[hsl(var(--status-done))]" />
    case 'failed':
      return <AlertCircle className="w-4 h-4 text-[hsl(var(--status-failed))]" />
    default:
      return <Circle className="w-4 h-4 text-muted-foreground/50" />
  }
}

export default TaskPill

