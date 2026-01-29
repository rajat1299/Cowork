/**
 * AgentCard Component
 * 
 * A glassmorphic card representing an AI agent.
 * Apple-inspired design with subtle animations.
 * 
 * Features:
 * - Glass effect with backdrop blur
 * - Breathing animation when active
 * - Progress arc indicator
 * - Minimal, purposeful UI
 */

import { useMemo } from 'react'
import { cn } from '@/lib/utils'
import { Terminal, Globe, FileText, Image, Bot } from 'lucide-react'
import type { AgentCardProps } from './types'
import { getAgentDisplayName, getAgentAccentClass, getAgentProgress, normalizeTaskState } from './types'
import { TaskPill } from './TaskPill'
import { ToolkitActivityList } from './ToolkitActivity'

// Icon mapping for agent types
const AgentIcons: Record<string, typeof Bot> = {
  developer_agent: Terminal,
  search_agent: Globe,
  document_agent: FileText,
  multi_modal_agent: Image,
}

export function AgentCard({
  agent,
  isActive,
  isMuted,
  onSelect,
  className
}: AgentCardProps) {
  const Icon = AgentIcons[agent.type] || Bot
  const accentClass = getAgentAccentClass(agent.type)
  const progress = useMemo(() => getAgentProgress(agent), [agent.tasks])
  const displayName = getAgentDisplayName(agent.type)

  // Count tasks by status
  const taskCounts = useMemo(() => {
    let running = 0, completed = 0, waiting = 0, failed = 0
    agent.tasks.forEach(task => {
      const state = normalizeTaskState(task.state)
      if (state === 'running') running++
      else if (state === 'completed') completed++
      else if (state === 'failed') failed++
      else waiting++
    })
    return { running, completed, waiting, failed, total: agent.tasks.length }
  }, [agent.tasks])

  // Show recent toolkit activity
  const recentActivity = useMemo(() =>
    agent.toolkitActivity.slice(-5).reverse()
    , [agent.toolkitActivity])

  return (
    <button
      onClick={onSelect}
      className={cn(
        // Base card with gradient bg
        'workflow-card relative min-w-[280px] max-w-[320px] text-left',
        accentClass,

        // State variants
        isActive && 'workflow-card-active animate-breathe',
        isMuted && 'workflow-card-muted',

        // Hover/focus states (only when not muted)
        !isMuted && 'hover:scale-[1.01] focus:outline-none focus:ring-2 focus:ring-[var(--agent-color)]/30',

        className
      )}
    >
      {/* Inner content with subtle overlay for readability */}
      <div className="relative z-10 flex flex-col p-5 bg-black/20 dark:bg-black/30 backdrop-blur-[2px] rounded-2xl h-full">

        {/* ===== Header ===== */}
        <div className="flex items-start justify-between mb-4">
          {/* Agent identity */}
          <div className="flex items-center gap-3">
            {/* Icon with accent glow */}
            <div className={cn(
              'relative p-2.5 rounded-xl transition-all duration-500',
              isActive
                ? 'bg-white/20'
                : 'bg-white/10'
            )}>
              <Icon className={cn(
                'w-5 h-5 transition-colors duration-300',
                isActive
                  ? 'text-white'
                  : 'text-white/70'
              )} />

              {/* Active glow effect */}
              {isActive && (
                <span className="absolute inset-0 rounded-xl bg-white/10 blur-md -z-10" />
              )}
            </div>

            {/* Name */}
            <div>
              <h3 className={cn(
                'font-medium text-base transition-colors duration-300',
                isActive ? 'text-white' : 'text-white/80'
              )}>
                {displayName}
              </h3>

              {/* Status subtitle */}
              <p className="text-xs text-white/50 mt-0.5">
                {agent.status === 'active' && taskCounts.running > 0 && (
                  <span className="text-white/90">
                    Working on {taskCounts.running} task{taskCounts.running > 1 ? 's' : ''}
                  </span>
                )}
                {agent.status === 'idle' && taskCounts.waiting > 0 && (
                  <span>{taskCounts.waiting} pending</span>
                )}
                {agent.status === 'done' && (
                  <span>{taskCounts.completed} completed</span>
                )}
                {agent.tasks.length === 0 && (
                  <span>Standing by</span>
                )}
              </p>
            </div>
          </div>

          {/* Progress indicator */}
          {agent.tasks.length > 0 && (
            <ProgressRing progress={progress} isActive={isActive} />
          )}
        </div>

        {/* ===== Tasks ===== */}
        {agent.tasks.length > 0 && (
          <div className="space-y-1.5 mb-4">
            {agent.tasks.slice(0, 4).map(task => (
              <TaskPill
                key={task.id}
                task={task}
                className="w-full"
              />
            ))}

            {agent.tasks.length > 4 && (
              <p className="text-xs text-muted-foreground/50 px-3 py-1">
                +{agent.tasks.length - 4} more tasks
              </p>
            )}
          </div>
        )}

        {/* ===== Toolkit Activity ===== */}
        {recentActivity.length > 0 && (
          <div className={cn(
            'pt-3 border-t transition-colors duration-300',
            isActive
              ? 'border-[var(--agent-color)]/10'
              : 'border-muted/30'
          )}>
            <ToolkitActivityList
              activities={recentActivity}
              maxVisible={2}
            />
          </div>
        )}

        {/* ===== Empty state ===== */}
        {agent.tasks.length === 0 && recentActivity.length === 0 && (
          <div className="flex-1 flex items-center justify-center py-6">
            <p className="text-sm text-white/60 text-center">
              Ready to assist
            </p>
          </div>
        )}
      </div>{/* Close inner content overlay */}
    </button>
  )
}

/**
 * Minimal progress ring indicator
 */
function ProgressRing({ progress, isActive }: { progress: number; isActive: boolean }) {
  const circumference = 2 * Math.PI * 14 // radius = 14
  const offset = circumference - (progress / 100) * circumference

  return (
    <div className="relative w-10 h-10">
      <svg className="w-10 h-10 -rotate-90" viewBox="0 0 32 32" aria-hidden="true">
        {/* Background circle */}
        <circle
          cx="16"
          cy="16"
          r="14"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-white/20"
        />

        {/* Progress arc */}
        <circle
          cx="16"
          cy="16"
          r="14"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={cn(
            'transition-all duration-700 ease-smooth',
            isActive
              ? 'text-white'
              : 'text-white/60'
          )}
        />
      </svg>

      {/* Percentage text */}
      <span className={cn(
        'absolute inset-0 flex items-center justify-center',
        'text-xs font-medium',
        isActive ? 'text-white' : 'text-white/70'
      )}>
        {progress}
      </span>
    </div>
  )
}

export default AgentCard

