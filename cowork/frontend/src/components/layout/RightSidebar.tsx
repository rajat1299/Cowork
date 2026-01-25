import { useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  FolderOpen,
  FileText,
  Image,
  FileCode,
  Loader2,
  Plus,
  X,
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { useChatStore } from '../../stores/chatStore'
import type { ProgressStep, ArtifactInfo } from '../../types/chat'

interface RightSidebarProps {
  className?: string
}

export function RightSidebar({ className }: RightSidebarProps) {
  const activeTask = useChatStore((s) => s.getActiveTask())

  // Determine if we have an active/running task
  const hasActiveTask = activeTask && activeTask.messages.length > 0
  const isTaskRunning = activeTask?.status === 'running' || activeTask?.status === 'pending'

  return (
    <aside
      className={cn(
        'w-80 h-full flex flex-col',
        'border-l border-dark-border',
        'bg-dark-bg',
        className
      )}
    >
      {hasActiveTask ? (
        // Active task view - detailed progress
        <ActiveTaskSidebar task={activeTask} isRunning={isTaskRunning} />
      ) : (
        // New chat / no task view - placeholders + connectors
        <NewChatSidebar />
      )}
    </aside>
  )
}

// ============ New Chat Sidebar (Original Design) ============

function NewChatSidebar() {
  return (
    <>
      {/* Main sections */}
      <div className="flex-1 overflow-y-auto scrollbar-hide p-4 space-y-6">
        {/* Progress Section */}
        <Section title="Progress">
          <div className="flex items-center gap-2">
            {/* Progress circles */}
            <ProgressCircle status="completed" />
            <div className="w-4 h-px bg-dark-border" />
            <ProgressCircle status="completed" />
            <div className="w-4 h-px bg-dark-border" />
            <ProgressCircle status="active" />
            <div className="w-4 h-px bg-dark-border" />
            <ProgressCircle status="pending" />
          </div>
          <p className="text-[13px] text-ink-subtle mt-3">
            Steps will show as the task unfolds.
          </p>
        </Section>

        {/* Artifacts Section */}
        <Section title="Artifacts">
          <div className="grid grid-cols-3 gap-2">
            <ArtifactPlaceholder />
          </div>
          <p className="text-[13px] text-ink-subtle mt-3">
            Outputs created during the task land here.
          </p>
        </Section>

        {/* Context Section */}
        <Section title="Context">
          <div className="flex items-center gap-2">
            <ContextPlaceholder />
            <ContextPlaceholder active />
          </div>
          <p className="text-[13px] text-ink-subtle mt-3">
            Track the tools and files in use as Claude works.
          </p>
        </Section>
      </div>

      {/* Suggested Connectors */}
      <SuggestedConnectors />
    </>
  )
}

// ============ Active Task Sidebar (New Design) ============

interface ActiveTaskSidebarProps {
  task: NonNullable<ReturnType<typeof useChatStore.getState>['getActiveTask']>
  isRunning: boolean
}

function ActiveTaskSidebar({ task, isRunning }: ActiveTaskSidebarProps) {
  const progressSteps = task?.progressSteps || []
  const artifacts = task?.artifacts || []

  // Extract files from artifacts for working folder
  const workingFiles = artifacts.filter((a) => a.type === 'file' || a.type === 'code')

  return (
    <div className="flex-1 overflow-y-auto scrollbar-hide">
      {/* Progress Section */}
      <CollapsibleSection title="Progress" defaultOpen>
        {progressSteps.length === 0 ? (
          <div className="px-4 pb-4">
            <div className="flex items-center gap-2 mb-3">
              <ProgressCircle status={isRunning ? 'active' : 'pending'} />
              <div className="w-4 h-px bg-dark-border" />
              <ProgressCircle status="pending" />
              <div className="w-4 h-px bg-dark-border" />
              <ProgressCircle status="pending" />
            </div>
            <p className="text-[13px] text-ink-subtle">
              Steps will show as the task unfolds.
            </p>
          </div>
        ) : (
          <div className="px-4 pb-4 space-y-0">
            {progressSteps.map((step, index) => (
              <ProgressStepItem
                key={`${step.step}-${index}`}
                step={step}
                stepNumber={index + 1}
                isLast={index === progressSteps.length - 1}
              />
            ))}
          </div>
        )}
      </CollapsibleSection>

      {/* Working folder Section */}
      <CollapsibleSection title="Working folder" defaultOpen>
        <div className="px-4 pb-4">
          <WorkingFolderTree files={workingFiles} />
        </div>
      </CollapsibleSection>

      {/* Scratchpad Section */}
      <CollapsibleSection title="Scratchpad" defaultOpen={false}>
        <div className="px-4 pb-4">
          {artifacts.length === 0 ? (
            <p className="text-[13px] text-ink-subtle">
              Files created or viewed will appear here.
            </p>
          ) : (
            <div className="space-y-1">
              {artifacts.slice(0, 10).map((artifact, idx) => (
                <ScratchpadItem key={artifact.id || idx} artifact={artifact} />
              ))}
              {artifacts.length > 10 && (
                <button className="text-[12px] text-ink-muted hover:text-ink transition-colors">
                  Show {artifacts.length - 10} more
                </button>
              )}
            </div>
          )}
        </div>
      </CollapsibleSection>

      {/* Context Section */}
      <CollapsibleSection title="Context" defaultOpen={false}>
        <div className="px-4 pb-4">
          <div className="flex gap-2 mb-3">
            <ContextCard type="tools" active={isRunning} />
            <ContextCard type="files" active={artifacts.length > 0} />
          </div>
          <p className="text-[12px] text-ink-subtle">
            Track tools and referenced files used in this task.
          </p>
        </div>
      </CollapsibleSection>
    </div>
  )
}

// ============ Suggested Connectors Section ============

function SuggestedConnectors() {
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  return (
    <div className="border-t border-dark-border p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[14px] font-medium text-ink">Suggested connectors</h3>
        <button
          onClick={() => setDismissed(true)}
          className="p-1 rounded hover:bg-dark-surface transition-colors"
        >
          <X size={14} className="text-ink-subtle" />
        </button>
      </div>
      <p className="text-[12px] text-ink-subtle mb-4">
        Cowork uses connectors to browse websites, manage tasks, and more.
      </p>

      <div className="space-y-2">
        <ConnectorItem icon="chrome" label="Claude in Chrome" />
        <ConnectorItem icon="notion" label="Notion" />
        <ConnectorItem icon="linear" label="Linear" />
      </div>

      <button className="flex items-center gap-1 mt-4 text-[13px] text-ink-muted hover:text-ink transition-colors">
        <span>See all connectors</span>
        <ChevronRight size={14} />
      </button>
    </div>
  )
}

// ============ Shared Components ============

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-[14px] font-medium text-ink mb-3">{title}</h3>
      {children}
    </div>
  )
}

function ProgressCircle({ status }: { status: 'completed' | 'active' | 'pending' }) {
  return (
    <div
      className={cn(
        'w-6 h-6 rounded-full flex items-center justify-center',
        status === 'completed' && 'bg-warm-beige/20',
        status === 'active' && 'bg-burnt/20 ring-2 ring-burnt/30',
        status === 'pending' && 'bg-dark-surface border border-dark-border'
      )}
    >
      {status === 'completed' && (
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path
            d="M2.5 6L5 8.5L9.5 4"
            stroke="#F5E8D8"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
      {status === 'active' && <div className="w-2 h-2 rounded-full bg-burnt" />}
    </div>
  )
}

function ArtifactPlaceholder() {
  return (
    <div className="aspect-[4/3] rounded-lg bg-dark-surface border border-dark-border flex items-center justify-center">
      <div className="space-y-1">
        <div className="w-6 h-1 bg-ink-faint rounded" />
        <div className="w-8 h-1 bg-ink-faint rounded" />
        <div className="w-5 h-1 bg-ink-faint rounded" />
      </div>
    </div>
  )
}

function ContextPlaceholder({ active = false }: { active?: boolean }) {
  return (
    <div
      className={cn(
        'w-12 h-10 rounded-lg flex items-center justify-center',
        'border transition-all duration-200',
        active ? 'bg-dark-elevated border-burnt/30' : 'bg-dark-surface border-dark-border'
      )}
    >
      <div className="space-y-0.5">
        <div className="w-5 h-0.5 bg-ink-faint rounded" />
        <div className="w-6 h-0.5 bg-ink-faint rounded" />
        <div className="w-4 h-0.5 bg-ink-faint rounded" />
      </div>
    </div>
  )
}

function ConnectorItem({ icon, label }: { icon: string; label: string }) {
  return (
    <div
      className={cn(
        'flex items-center justify-between p-3 rounded-xl',
        'bg-dark-surface border border-dark-border',
        'hover:border-ink-faint transition-all duration-200',
        'group cursor-pointer'
      )}
    >
      <div className="flex items-center gap-3">
        <ConnectorIcon type={icon} />
        <span className="text-[13px] text-ink-muted group-hover:text-ink transition-colors">
          {label}
        </span>
      </div>
      <button
        className={cn(
          'w-6 h-6 rounded-md flex items-center justify-center',
          'bg-dark-elevated text-ink-subtle',
          'hover:bg-burnt hover:text-white',
          'transition-all duration-200'
        )}
      >
        <Plus size={14} strokeWidth={2} />
      </button>
    </div>
  )
}

function ConnectorIcon({ type }: { type: string }) {
  const baseClass = 'w-6 h-6 rounded flex items-center justify-center'

  switch (type) {
    case 'chrome':
      return (
        <div className={cn(baseClass, 'bg-gradient-to-br from-red-500 via-yellow-400 to-green-500')}>
          <div className="w-2.5 h-2.5 rounded-full bg-white" />
        </div>
      )
    case 'notion':
      return (
        <div className={cn(baseClass, 'bg-white')}>
          <span className="text-[10px] font-bold text-black">N</span>
        </div>
      )
    case 'linear':
      return (
        <div className={cn(baseClass, 'bg-[#5E6AD2]')}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="white">
            <path d="M0.5 9.5L9.5 0.5L11.5 2.5L2.5 11.5L0.5 9.5Z" />
          </svg>
        </div>
      )
    default:
      return <div className={cn(baseClass, 'bg-dark-elevated')} />
  }
}

// ============ Collapsible Section (for Active Task) ============

interface CollapsibleSectionProps {
  title: string
  defaultOpen?: boolean
  children: React.ReactNode
}

function CollapsibleSection({ title, defaultOpen = true, children }: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <div className="border-b border-dark-border">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'w-full flex items-center justify-between px-4 py-3',
          'hover:bg-dark-surface/50 transition-colors'
        )}
      >
        <h3 className="text-[14px] font-medium text-ink">{title}</h3>
        {isOpen ? (
          <ChevronDown size={16} className="text-ink-muted" />
        ) : (
          <ChevronRight size={16} className="text-ink-muted" />
        )}
      </button>
      {isOpen && children}
    </div>
  )
}

// ============ Progress Step Item ============

interface ProgressStepItemProps {
  step: ProgressStep
  stepNumber: number
  isLast: boolean
}

function ProgressStepItem({ step, stepNumber, isLast }: ProgressStepItemProps) {
  const isActive = step.status === 'active'
  const isCompleted = step.status === 'completed'
  const isPending = step.status === 'pending'

  return (
    <div className="flex gap-3">
      {/* Step indicator */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            'w-6 h-6 rounded-full flex items-center justify-center text-[12px] font-medium',
            'transition-colors',
            isCompleted && 'bg-warm-beige/20 text-warm-beige',
            isActive && 'bg-burnt text-white',
            isPending && 'bg-dark-surface border border-dark-border text-ink-subtle'
          )}
        >
          {isActive ? <Loader2 size={12} className="animate-spin" /> : stepNumber}
        </div>
        {/* Vertical line connecting steps */}
        {!isLast && (
          <div
            className={cn(
              'w-px flex-1 min-h-[20px]',
              isCompleted ? 'bg-warm-beige/30' : 'bg-dark-border'
            )}
          />
        )}
      </div>

      {/* Step content */}
      <div className={cn('flex-1 pb-4', isLast && 'pb-0')}>
        <p
          className={cn(
            'text-[13px] leading-relaxed',
            isActive && 'text-ink',
            isCompleted && 'text-ink-muted',
            isPending && 'text-ink-subtle'
          )}
        >
          {step.label}
        </p>
        {/* Show additional data if present */}
        {step.data?.detail != null && (
          <p className="text-[11px] text-ink-subtle mt-0.5">{String(step.data.detail)}</p>
        )}
      </div>
    </div>
  )
}

// ============ Working Folder Tree ============

interface WorkingFolderTreeProps {
  files: ArtifactInfo[]
}

function WorkingFolderTree({ files }: WorkingFolderTreeProps) {
  const rootDir = 'Desktop' // Default for demo

  if (files.length === 0) {
    return (
      <div className="flex items-center gap-2 text-ink-muted">
        <FolderOpen size={16} />
        <span className="text-[13px]">No files in context</span>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {/* Root folder */}
      <div className="flex items-center gap-2 text-ink">
        <FolderOpen size={16} className="text-burnt" />
        <span className="text-[13px] font-medium">{rootDir}</span>
      </div>

      {/* Files */}
      <div className="ml-4 space-y-0.5">
        {files.slice(0, 6).map((file, idx) => (
          <FileItem key={file.id || idx} file={file} />
        ))}
        {files.length > 6 && (
          <button className="flex items-center gap-1 text-[12px] text-ink-muted hover:text-ink transition-colors py-1">
            <span>Show {files.length - 6} more</span>
          </button>
        )}
      </div>
    </div>
  )
}

function FileItem({ file }: { file: ArtifactInfo }) {
  const getIcon = () => {
    if (file.type === 'image' || file.name?.match(/\.(png|jpg|jpeg|gif|svg)$/i)) {
      return <Image size={14} className="text-ink-muted" />
    }
    if (file.type === 'code' || file.name?.match(/\.(ts|tsx|js|jsx|py|json)$/i)) {
      return <FileCode size={14} className="text-ink-muted" />
    }
    return <FileText size={14} className="text-ink-muted" />
  }

  const displayName = file.name || 'Untitled'
  const truncatedName = displayName.length > 30 ? displayName.slice(0, 27) + '...' : displayName

  return (
    <div className="flex items-center gap-2 py-0.5 group">
      {getIcon()}
      <span className="text-[12px] text-ink-muted group-hover:text-ink transition-colors truncate">
        {truncatedName}
      </span>
    </div>
  )
}

// ============ Scratchpad Item ============

interface ScratchpadItemProps {
  artifact: ArtifactInfo
}

function ScratchpadItem({ artifact }: ScratchpadItemProps) {
  const getIcon = () => {
    if (artifact.type === 'image') return <Image size={14} />
    if (artifact.type === 'code') return <FileCode size={14} />
    return <FileText size={14} />
  }

  const action = artifact.action || null

  return (
    <div
      className={cn(
        'flex items-center justify-between gap-2 p-2 rounded-lg',
        'bg-dark-surface/50 hover:bg-dark-surface',
        'transition-colors cursor-pointer group'
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        <div className="text-ink-muted">{getIcon()}</div>
        <span className="text-[12px] text-ink-muted group-hover:text-ink truncate">
          {artifact.name || 'Untitled'}
        </span>
      </div>
      {action && <span className="text-[10px] text-ink-subtle flex-shrink-0">{action}</span>}
    </div>
  )
}

// ============ Context Card ============

interface ContextCardProps {
  type: 'tools' | 'files'
  active?: boolean
}

function ContextCard({ type, active = false }: ContextCardProps) {
  return (
    <div
      className={cn(
        'flex-1 p-3 rounded-xl',
        'border transition-all duration-200',
        active ? 'bg-dark-surface border-burnt/30' : 'bg-dark-surface/50 border-dark-border'
      )}
    >
      <div className="flex items-center gap-2 mb-2">
        {type === 'tools' ? (
          <div className="w-6 h-6 rounded bg-dark-elevated flex items-center justify-center">
            <div className="grid grid-cols-2 gap-0.5">
              <div className="w-1.5 h-1.5 bg-ink-faint rounded-sm" />
              <div className="w-1.5 h-1.5 bg-ink-faint rounded-sm" />
              <div className="w-1.5 h-1.5 bg-ink-faint rounded-sm" />
              <div className="w-1.5 h-1.5 bg-ink-faint rounded-sm" />
            </div>
          </div>
        ) : (
          <div className="w-6 h-6 rounded bg-dark-elevated flex items-center justify-center">
            <FileText size={12} className="text-ink-muted" />
          </div>
        )}
        <span className="text-[12px] text-ink-muted capitalize">{type}</span>
      </div>
      {active && (
        <div className="flex items-center gap-1">
          <div className="w-1.5 h-1.5 rounded-full bg-burnt animate-pulse" />
          <span className="text-[10px] text-burnt">In use</span>
        </div>
      )}
    </div>
  )
}
