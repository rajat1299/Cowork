/**
 * ToolkitActivity Component
 * 
 * Displays toolkit activations as ephemeral, minimal indicators.
 * Designed to communicate activity without overwhelming text.
 */

import { cn } from '@/lib/utils'
import { Zap, Check } from 'lucide-react'
import type { ToolkitActivityProps } from './types'

export function ToolkitActivity({ activity, className }: ToolkitActivityProps) {
  const isRunning = activity.status === 'running'
  
  // Format method name for display (remove underscores, title case)
  const methodDisplay = activity.methodName
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
  
  // Truncate message
  const messagePreview = activity.message.length > 40
    ? activity.message.slice(0, 37) + '...'
    : activity.message

  return (
    <div
      className={cn(
        // Base styles
        'flex items-center gap-2 py-1.5 px-2 rounded-lg',
        'text-xs transition-all duration-300 ease-smooth',
        
        // Running state - more prominent
        isRunning && [
          'bg-[hsl(var(--status-active)/0.08)]',
          'text-foreground',
        ],
        
        // Done state - fade out
        !isRunning && [
          'bg-transparent',
          'text-muted-foreground/60',
        ],
        
        className
      )}
    >
      {/* Activity icon */}
      <span className={cn(
        'flex-shrink-0 transition-all duration-300',
        isRunning && 'text-[hsl(var(--status-active))]',
        !isRunning && 'text-muted-foreground/40'
      )}>
        {isRunning ? (
          <Zap className="w-3 h-3 animate-pulse" />
        ) : (
          <Check className="w-3 h-3" />
        )}
      </span>
      
      {/* Toolkit info */}
      <span className="flex-1 min-w-0 flex items-center gap-1.5 truncate">
        <span className={cn(
          'font-medium',
          isRunning && 'text-foreground',
          !isRunning && 'text-muted-foreground/60'
        )}>
          {methodDisplay}
        </span>
        
        {messagePreview && (
          <>
            <span className="text-muted-foreground/30">·</span>
            <span className="truncate opacity-60">
              {messagePreview}
            </span>
          </>
        )}
      </span>
    </div>
  )
}

/**
 * ToolkitActivityList
 * 
 * Shows the most recent toolkit activities for an agent.
 * Auto-collapses older entries.
 */
export function ToolkitActivityList({ 
  activities, 
  maxVisible = 3,
  className 
}: { 
  activities: ToolkitActivityProps['activity'][]
  maxVisible?: number
  className?: string
}) {
  // Show most recent activities, with running ones always visible
  const runningActivities = activities.filter(a => a.status === 'running')
  const doneActivities = activities.filter(a => a.status === 'done')
  
  // Prioritize running activities, fill rest with done
  const visibleActivities = [
    ...runningActivities,
    ...doneActivities.slice(0, Math.max(0, maxVisible - runningActivities.length))
  ].slice(0, maxVisible)

  if (visibleActivities.length === 0) {
    return null
  }

  return (
    <div className={cn('space-y-0.5', className)}>
      {visibleActivities.map(activity => (
        <ToolkitActivity 
          key={activity.id} 
          activity={activity}
        />
      ))}
      
      {/* Show count of hidden activities */}
      {activities.length > maxVisible && (
        <div className="text-xs text-muted-foreground/40 px-2 py-1">
          +{activities.length - maxVisible} more
        </div>
      )}
    </div>
  )
}

export default ToolkitActivity

