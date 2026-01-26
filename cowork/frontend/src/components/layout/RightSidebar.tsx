import { useState, useEffect } from 'react'
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
  Camera,
  ExternalLink,
  Maximize2,
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { useChatStore } from '../../stores/chatStore'
import { useSnapshots } from '../../hooks/useSnapshots'
import type { ArtifactInfo, TaskInfo } from '../../types/chat'
import type { Snapshot } from '../../api/coreApi'

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
        'border-l border-border',
        'bg-card/80 backdrop-blur-xl',
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
            <div className="w-4 h-px bg-border" />
            <ProgressCircle status="completed" />
            <div className="w-4 h-px bg-border" />
            <ProgressCircle status="active" />
            <div className="w-4 h-px bg-border" />
            <ProgressCircle status="pending" />
          </div>
          <p className="text-[13px] text-muted-foreground mt-3">
            Steps will show as the task unfolds.
          </p>
        </Section>

        {/* Artifacts Section */}
        <Section title="Artifacts">
          <div className="grid grid-cols-3 gap-2">
            <ArtifactPlaceholder />
          </div>
          <p className="text-[13px] text-muted-foreground mt-3">
            Outputs created during the task land here.
          </p>
        </Section>

        {/* Context Section */}
        <Section title="Context">
          <div className="flex items-center gap-2">
            <ContextPlaceholder />
            <ContextPlaceholder active />
          </div>
          <p className="text-[13px] text-muted-foreground mt-3">
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
  task: NonNullable<ReturnType<ReturnType<typeof useChatStore.getState>['getActiveTask']>>
  isRunning: boolean
}

function ActiveTaskSidebar({ task, isRunning }: ActiveTaskSidebarProps) {
  const subtasks: TaskInfo[] = task?.subtasks || []
  const artifacts: ArtifactInfo[] = task?.artifacts || []
  const taskId = task?.id

  // Snapshots state
  const { snapshots, fetchSnapshots, getImageUrl } = useSnapshots()
  const [selectedSnapshot, setSelectedSnapshot] = useState<Snapshot | null>(null)

  // Fetch snapshots when task changes
  useEffect(() => {
    if (taskId) {
      fetchSnapshots(taskId)
    }
  }, [taskId, fetchSnapshots])

  // Extract files from artifacts for working folder
  const workingFiles = artifacts.filter((a) => a.type === 'file' || a.type === 'code')

  return (
    <>
      <div className="flex-1 overflow-y-auto scrollbar-hide">
        {/* Progress Section - Now shows subtasks, not internal steps */}
        <CollapsibleSection title="Progress" defaultOpen>
          {subtasks.length === 0 ? (
            <div className="px-4 pb-4">
              <div className="flex items-center gap-2 mb-3">
                <ProgressCircle status={isRunning ? 'active' : 'pending'} />
                <div className="w-4 h-px bg-border" />
                <ProgressCircle status="pending" />
                <div className="w-4 h-px bg-border" />
                <ProgressCircle status="pending" />
              </div>
              <p className="text-[13px] text-muted-foreground">
                {isRunning ? 'Analyzing your request...' : 'Steps will show as the task unfolds.'}
              </p>
            </div>
          ) : (
            <div className="px-4 pb-4 space-y-0">
              {subtasks.map((subtask, index) => (
                <SubtaskProgressItem
                  key={subtask.id}
                  subtask={subtask}
                  stepNumber={index + 1}
                  isLast={index === subtasks.length - 1}
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

        {/* Snapshots Section */}
        <CollapsibleSection title="Snapshots" defaultOpen={snapshots.length > 0}>
          <div className="px-4 pb-4">
            {snapshots.length === 0 ? (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Camera size={16} />
                <span className="text-[13px]">No snapshots captured</span>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {snapshots.slice(0, 6).map((snapshot) => (
                  <SnapshotThumbnail
                    key={snapshot.id}
                    snapshot={snapshot}
                    imageUrl={getImageUrl(snapshot.id)}
                    onClick={() => setSelectedSnapshot(snapshot)}
                  />
                ))}
              </div>
            )}
            {snapshots.length > 6 && (
              <button className="text-[12px] text-muted-foreground hover:text-foreground transition-colors mt-2">
                View all {snapshots.length} snapshots
              </button>
            )}
          </div>
        </CollapsibleSection>

        {/* Scratchpad Section */}
        <CollapsibleSection title="Scratchpad" defaultOpen={false}>
          <div className="px-4 pb-4">
            {artifacts.length === 0 ? (
              <p className="text-[13px] text-muted-foreground">
                Files created or viewed will appear here.
              </p>
            ) : (
              <div className="space-y-1">
                {artifacts.slice(0, 10).map((artifact, idx) => (
                  <ScratchpadItem key={artifact.id || idx} artifact={artifact} />
                ))}
                {artifacts.length > 10 && (
                  <button className="text-[12px] text-muted-foreground hover:text-foreground transition-colors">
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
            <p className="text-[12px] text-muted-foreground">
              Track tools and referenced files used in this task.
            </p>
          </div>
        </CollapsibleSection>
      </div>

      {/* Snapshot Viewer Modal */}
      {selectedSnapshot && (
        <SnapshotViewerModal
          snapshot={selectedSnapshot}
          imageUrl={getImageUrl(selectedSnapshot.id)}
          onClose={() => setSelectedSnapshot(null)}
        />
      )}
    </>
  )
}

// ============ Suggested Connectors Section ============

function SuggestedConnectors() {
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  return (
    <div className="border-t border-border p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[14px] font-medium text-foreground">Suggested connectors</h3>
        <button
          onClick={() => setDismissed(true)}
          className="p-1 rounded hover:bg-secondary transition-colors"
        >
          <X size={14} className="text-muted-foreground" />
        </button>
      </div>
      <p className="text-[12px] text-muted-foreground mb-4">
        Cowork uses connectors to browse websites, manage tasks, and more.
      </p>

      <div className="space-y-2">
        <ConnectorItem icon="chrome" label="Claude in Chrome" />
        <ConnectorItem icon="notion" label="Notion" />
        <ConnectorItem icon="linear" label="Linear" />
      </div>

      <button className="flex items-center gap-1 mt-4 text-[13px] text-muted-foreground hover:text-foreground transition-colors">
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
      <h3 className="text-[14px] font-medium text-foreground mb-3">{title}</h3>
      {children}
    </div>
  )
}

function ProgressCircle({ status }: { status: 'completed' | 'active' | 'pending' }) {
  return (
    <div
      className={cn(
        'w-6 h-6 rounded-full flex items-center justify-center',
        status === 'completed' && 'bg-foreground/10',
        status === 'active' && 'bg-burnt/20 ring-2 ring-burnt/30',
        status === 'pending' && 'bg-secondary border border-border'
      )}
    >
      {status === 'completed' && (
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path
            d="M2.5 6L5 8.5L9.5 4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-foreground"
          />
        </svg>
      )}
      {status === 'active' && <div className="w-2 h-2 rounded-full bg-burnt" />}
    </div>
  )
}

function ArtifactPlaceholder() {
  return (
    <div className="aspect-[4/3] rounded-lg bg-secondary border border-border flex items-center justify-center">
      <div className="space-y-1">
        <div className="w-6 h-1 bg-muted-foreground/20 rounded" />
        <div className="w-8 h-1 bg-muted-foreground/20 rounded" />
        <div className="w-5 h-1 bg-muted-foreground/20 rounded" />
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
        active ? 'bg-accent border-burnt/30' : 'bg-secondary border-border'
      )}
    >
      <div className="space-y-0.5">
        <div className="w-5 h-0.5 bg-muted-foreground/20 rounded" />
        <div className="w-6 h-0.5 bg-muted-foreground/20 rounded" />
        <div className="w-4 h-0.5 bg-muted-foreground/20 rounded" />
      </div>
    </div>
  )
}

function ConnectorItem({ icon, label }: { icon: string; label: string }) {
  return (
    <div
      className={cn(
        'flex items-center justify-between p-3 rounded-xl',
        'bg-secondary border border-border',
        'hover:border-foreground/30 transition-all duration-200',
        'group cursor-pointer'
      )}
    >
      <div className="flex items-center gap-3">
        <ConnectorIcon type={icon} />
        <span className="text-[13px] text-muted-foreground group-hover:text-foreground transition-colors">
          {label}
        </span>
      </div>
      <button
        className={cn(
          'w-6 h-6 rounded-md flex items-center justify-center',
          'bg-accent text-muted-foreground',
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
      return <div className={cn(baseClass, 'bg-accent')} />
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
    <div className="border-b border-border">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'w-full flex items-center justify-between px-4 py-3',
          'hover:bg-secondary/50 transition-colors'
        )}
      >
        <h3 className="text-[14px] font-medium text-foreground">{title}</h3>
        {isOpen ? (
          <ChevronDown size={16} className="text-muted-foreground" />
        ) : (
          <ChevronRight size={16} className="text-muted-foreground" />
        )}
      </button>
      {isOpen && children}
    </div>
  )
}

// ============ Subtask Progress Item (New - shows actual task progress) ============

interface SubtaskProgressItemProps {
  subtask: TaskInfo
  stepNumber: number
  isLast: boolean
}

function SubtaskProgressItem({ subtask, stepNumber, isLast }: SubtaskProgressItemProps) {
  const isActive = subtask.status === 'running'
  const isCompleted = subtask.status === 'completed'
  const isFailed = subtask.status === 'failed'
  const isPending = subtask.status === 'pending' || subtask.status === 'paused'

  return (
    <div className="flex gap-3">
      {/* Step indicator */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            'w-6 h-6 rounded-full flex items-center justify-center text-[12px] font-medium',
            'transition-colors',
            isCompleted && 'bg-[hsl(var(--status-done)/0.2)] text-[hsl(var(--status-done))]',
            isActive && 'bg-burnt text-white',
            isFailed && 'bg-destructive/20 text-destructive',
            isPending && 'bg-secondary border border-border text-muted-foreground'
          )}
        >
          {isActive ? (
            <Loader2 size={12} className="animate-spin" />
          ) : isCompleted ? (
            '✓'
          ) : isFailed ? (
            '✗'
          ) : (
            stepNumber
          )}
        </div>
        {/* Vertical line connecting steps */}
        {!isLast && (
          <div
            className={cn(
              'w-px flex-1 min-h-[20px]',
              isCompleted ? 'bg-[hsl(var(--status-done)/0.3)]' : 'bg-border'
            )}
          />
        )}
      </div>

      {/* Step content */}
      <div className={cn('flex-1 pb-4', isLast && 'pb-0')}>
        <p
          className={cn(
            'text-[13px] leading-relaxed',
            isActive && 'text-foreground',
            isCompleted && 'text-muted-foreground',
            isFailed && 'text-destructive',
            isPending && 'text-muted-foreground'
          )}
        >
          {subtask.title}
        </p>
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
      <div className="flex items-center gap-2 text-muted-foreground">
        <FolderOpen size={16} />
        <span className="text-[13px]">No files in context</span>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {/* Root folder */}
      <div className="flex items-center gap-2 text-foreground">
        <FolderOpen size={16} className="text-burnt" />
        <span className="text-[13px] font-medium">{rootDir}</span>
      </div>

      {/* Files */}
      <div className="ml-4 space-y-0.5">
        {files.slice(0, 6).map((file, idx) => (
          <FileItem key={file.id || idx} file={file} />
        ))}
        {files.length > 6 && (
          <button className="flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground transition-colors py-1">
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
      return <Image size={14} className="text-muted-foreground" />
    }
    if (file.type === 'code' || file.name?.match(/\.(ts|tsx|js|jsx|py|json)$/i)) {
      return <FileCode size={14} className="text-muted-foreground" />
    }
    return <FileText size={14} className="text-muted-foreground" />
  }

  const displayName = file.name || 'Untitled'
  const truncatedName = displayName.length > 30 ? displayName.slice(0, 27) + '...' : displayName

  return (
    <div className="flex items-center gap-2 py-0.5 group">
      {getIcon()}
      <span className="text-[12px] text-muted-foreground group-hover:text-foreground transition-colors truncate">
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
        'bg-secondary/50 hover:bg-secondary',
        'transition-colors cursor-pointer group'
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        <div className="text-muted-foreground">{getIcon()}</div>
        <span className="text-[12px] text-muted-foreground group-hover:text-foreground truncate">
          {artifact.name || 'Untitled'}
        </span>
      </div>
      {action && <span className="text-[10px] text-muted-foreground flex-shrink-0">{action}</span>}
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
        active ? 'bg-secondary border-burnt/30' : 'bg-secondary/50 border-border'
      )}
    >
      <div className="flex items-center gap-2 mb-2">
        {type === 'tools' ? (
          <div className="w-6 h-6 rounded bg-accent flex items-center justify-center">
            <div className="grid grid-cols-2 gap-0.5">
              <div className="w-1.5 h-1.5 bg-muted-foreground/20 rounded-sm" />
              <div className="w-1.5 h-1.5 bg-muted-foreground/20 rounded-sm" />
              <div className="w-1.5 h-1.5 bg-muted-foreground/20 rounded-sm" />
              <div className="w-1.5 h-1.5 bg-muted-foreground/20 rounded-sm" />
            </div>
          </div>
        ) : (
          <div className="w-6 h-6 rounded bg-accent flex items-center justify-center">
            <FileText size={12} className="text-muted-foreground" />
          </div>
        )}
        <span className="text-[12px] text-muted-foreground capitalize">{type}</span>
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

// ============ Snapshot Components ============

interface SnapshotThumbnailProps {
  snapshot: Snapshot
  imageUrl: string
  onClick: () => void
}

function SnapshotThumbnail({ snapshot, imageUrl, onClick }: SnapshotThumbnailProps) {
  const [imageError, setImageError] = useState(false)

  return (
    <button
      onClick={onClick}
      className={cn(
        'relative aspect-video rounded-lg overflow-hidden',
        'border border-border hover:border-burnt/50',
        'transition-all duration-200 group',
        'bg-secondary'
      )}
    >
      {imageError ? (
        <div className="absolute inset-0 flex items-center justify-center">
          <Camera size={20} className="text-muted-foreground" />
        </div>
      ) : (
        <img
          src={imageUrl}
          alt={`Snapshot ${snapshot.id}`}
          className="w-full h-full object-cover"
          onError={() => setImageError(true)}
        />
      )}
      {/* Hover overlay */}
      <div
        className={cn(
          'absolute inset-0 bg-background/60 opacity-0 group-hover:opacity-100',
          'flex items-center justify-center transition-opacity'
        )}
      >
        <Maximize2 size={16} className="text-foreground" />
      </div>
      {/* URL indicator */}
      {snapshot.browser_url && (
        <div className="absolute bottom-1 left-1 right-1 px-1.5 py-0.5 bg-background/80 rounded text-[9px] text-muted-foreground truncate">
          {new URL(snapshot.browser_url).hostname}
        </div>
      )}
    </button>
  )
}

interface SnapshotViewerModalProps {
  snapshot: Snapshot
  imageUrl: string
  onClose: () => void
}

function SnapshotViewerModal({ snapshot, imageUrl, onClose }: SnapshotViewerModalProps) {
  const [imageError, setImageError] = useState(false)

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose])

  const formattedDate = new Date(snapshot.created_at).toLocaleString()

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/90 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className={cn(
          'relative max-w-4xl max-h-[90vh] w-full mx-4',
          'bg-secondary rounded-xl border border-border',
          'overflow-hidden shadow-2xl'
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-3">
            <Camera size={18} className="text-muted-foreground" />
            <div>
              <h3 className="text-[14px] font-medium text-foreground">Browser Snapshot</h3>
              <p className="text-[11px] text-muted-foreground">{formattedDate}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {snapshot.browser_url && (
              <a
                href={snapshot.browser_url}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg',
                  'text-[12px] text-muted-foreground hover:text-foreground',
                  'bg-accent hover:bg-background/50',
                  'transition-colors'
                )}
              >
                <ExternalLink size={12} />
                <span className="max-w-[200px] truncate">{snapshot.browser_url}</span>
              </a>
            )}
            <button
              onClick={onClose}
              className={cn(
                'p-2 rounded-lg',
                'text-muted-foreground hover:text-foreground',
                'hover:bg-accent transition-colors'
              )}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Image */}
        <div className="relative overflow-auto max-h-[calc(90vh-60px)] bg-background/50">
          {imageError ? (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
              <Camera size={40} className="mb-3" />
              <p className="text-[14px]">Failed to load snapshot</p>
            </div>
          ) : (
            <img
              src={imageUrl}
              alt={`Snapshot ${snapshot.id}`}
              className="w-full h-auto"
              onError={() => setImageError(true)}
            />
          )}
        </div>
      </div>
    </div>
  )
}
