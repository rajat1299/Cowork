import { useMemo, useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Check,
  Loader2,
  Circle,
  XCircle,
  FolderOpen,
  FileText,
  Code2,
  Image as ImageIcon,
  ExternalLink,
  Download,
  Clipboard,
} from 'lucide-react'
import { buildTurnExecutionView, type TurnCheckpoint } from '../../lib/execution'
import {
  canPreviewArtifact,
  dedupeArtifactsByCanonicalName,
  filterUserArtifacts,
  resolveArtifactUrl,
} from '../../lib/artifacts'
import { cn } from '../../lib/utils'
import { useChatStore } from '../../stores/chatStore'
import { useViewerStore } from '../../stores/viewerStore'
import type { ArtifactInfo } from '../../types/chat'

interface RightSidebarProps {
  className?: string
}

function renderArtifactIcon(type: ArtifactInfo['type']) {
  if (type === 'image') return <ImageIcon size={14} className="text-muted-foreground" />
  if (type === 'code') return <Code2 size={14} className="text-muted-foreground" />
  return <FileText size={14} className="text-muted-foreground" />
}

function checkpointIcon(checkpoint: TurnCheckpoint) {
  if (checkpoint.status === 'completed') {
    return <Check size={14} className="text-foreground" />
  }
  if (checkpoint.status === 'failed') {
    return <XCircle size={14} className="text-destructive" />
  }
  if (checkpoint.status === 'active') {
    return <Loader2 size={14} className="text-burnt animate-spin" />
  }
  return <Circle size={10} className="text-muted-foreground/60" />
}

function CollapsibleSection({
  title,
  defaultOpen,
  children,
}: {
  title: string
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen ?? true)
  return (
    <section className="border-b border-border/60">
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="w-full px-4 py-3 flex items-center justify-between text-left"
      >
        <span className="text-[15px] font-semibold text-foreground">{title}</span>
        {open ? (
          <ChevronDown size={16} className="text-muted-foreground" />
        ) : (
          <ChevronRight size={16} className="text-muted-foreground" />
        )}
      </button>
      {open ? <div className="px-4 pb-4">{children}</div> : null}
    </section>
  )
}

function ArtifactRow({ artifact }: { artifact: ArtifactInfo }) {
  const openArtifact = useViewerStore((state) => state.openArtifact)
  const url = resolveArtifactUrl(artifact.contentUrl, artifact.path)
  const previewable = canPreviewArtifact(artifact)

  const handleOpen = () => {
    if (!url) return
    if (previewable) {
      openArtifact(artifact)
      return
    }
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="rounded-lg border border-border/70 bg-secondary/30 p-2.5">
      <div className="flex items-start gap-2.5">
        <div className="w-7 h-7 rounded-md bg-secondary/80 border border-border flex items-center justify-center">
          {renderArtifactIcon(artifact.type)}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-foreground truncate">{artifact.name}</p>
          {artifact.path ? (
            <p className="text-[11px] text-muted-foreground truncate">{artifact.path}</p>
          ) : null}
        </div>
      </div>

      <div className="mt-2 flex items-center gap-1.5">
        {url ? (
          <button
            onClick={handleOpen}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-border text-[11px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
          >
            <ExternalLink size={12} />
            Open
          </button>
        ) : null}
        {url ? (
          <a
            href={url}
            download={artifact.name}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-border text-[11px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
          >
            <Download size={12} />
            Download
          </a>
        ) : null}
        {artifact.path ? (
          <button
            onClick={() => void navigator.clipboard.writeText(artifact.path || '')}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-border text-[11px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
          >
            <Clipboard size={12} />
            Copy path
          </button>
        ) : null}
      </div>
    </div>
  )
}

function NewChatSidebar() {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <section className="rounded-lg border border-border/60 bg-secondary/20 p-3">
        <h3 className="text-[14px] font-semibold text-foreground">Progress</h3>
        <p className="mt-2 text-[13px] text-muted-foreground">Checkpoints appear once a task starts.</p>
      </section>
      <section className="rounded-lg border border-border/60 bg-secondary/20 p-3">
        <h3 className="text-[14px] font-semibold text-foreground">Working folder</h3>
        <p className="mt-2 text-[13px] text-muted-foreground">Generated files and artifacts appear here.</p>
      </section>
      <section className="rounded-lg border border-border/60 bg-secondary/20 p-3">
        <h3 className="text-[14px] font-semibold text-foreground">Context</h3>
        <p className="mt-2 text-[13px] text-muted-foreground">Connectors and skills used in this chat will be listed here.</p>
      </section>
    </div>
  )
}

export function RightSidebar({ className }: RightSidebarProps) {
  const activeTask = useChatStore((state) => state.getActiveTask())

  const view = useMemo(() => {
    if (!activeTask) {
      return {
        checkpoints: [],
        connectors: [],
        skills: [],
      }
    }
    const derived = buildTurnExecutionView(activeTask.progressSteps)
    return {
      checkpoints: derived.checkpoints,
      connectors: derived.connectors,
      skills: derived.skills,
    }
  }, [activeTask])

  const artifacts = useMemo(() => {
    if (!activeTask) return []
    return dedupeArtifactsByCanonicalName(filterUserArtifacts([...activeTask.artifacts]))
  }, [activeTask])

  return (
    <aside
      className={cn(
        'w-80 h-full flex flex-col border-l border-border bg-card/80 backdrop-blur-xl',
        className
      )}
    >
      {!activeTask || activeTask.messages.length === 0 ? (
        <NewChatSidebar />
      ) : (
        <div className="flex-1 overflow-y-auto">
          <CollapsibleSection title="Progress" defaultOpen>
            {view.checkpoints.length === 0 ? (
              <p className="text-[13px] text-muted-foreground">Checkpoints appear as execution events arrive.</p>
            ) : (
              <ol className="space-y-2">
                {view.checkpoints.map((checkpoint) => (
                  <li key={checkpoint.id} className="flex items-start gap-2.5">
                    <div
                      className={cn(
                        'mt-0.5 w-5 h-5 rounded-full border flex items-center justify-center',
                        checkpoint.status === 'completed' && 'bg-foreground/10 border-transparent',
                        checkpoint.status === 'active' && 'border-burnt/50 bg-burnt/10',
                        checkpoint.status === 'failed' && 'border-destructive/60 bg-destructive/10',
                        checkpoint.status === 'pending' && 'border-border bg-secondary/40'
                      )}
                    >
                      {checkpointIcon(checkpoint)}
                    </div>
                    <span
                      title={checkpoint.fullLabel || checkpoint.label}
                      className={cn(
                        'text-[13px] leading-5',
                        checkpoint.status === 'completed' && 'text-muted-foreground line-through',
                        checkpoint.status === 'active' && 'text-foreground',
                        checkpoint.status === 'failed' && 'text-destructive',
                        checkpoint.status === 'pending' && 'text-muted-foreground'
                      )}
                    >
                      {checkpoint.label}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </CollapsibleSection>

          <CollapsibleSection title="Working folder" defaultOpen>
            {artifacts.length === 0 ? (
              <div className="flex items-center gap-2 text-muted-foreground">
                <FolderOpen size={14} />
                <p className="text-[13px]">No files in context</p>
              </div>
            ) : (
              <div className="space-y-2">
                {artifacts.slice(-8).map((artifact) => (
                  <ArtifactRow key={artifact.id} artifact={artifact} />
                ))}
              </div>
            )}
          </CollapsibleSection>

          <CollapsibleSection title="Context" defaultOpen>
            <div className="space-y-3">
              <div>
                <p className="text-[12px] uppercase tracking-wide text-muted-foreground mb-1.5">Connectors</p>
                {view.connectors.length === 0 ? (
                  <p className="text-[13px] text-muted-foreground">None used yet.</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {view.connectors.map((connector) => (
                      <span
                        key={connector}
                        className="px-2 py-1 rounded-full border border-border bg-secondary/40 text-[12px] text-foreground"
                      >
                        {connector}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <p className="text-[12px] uppercase tracking-wide text-muted-foreground mb-1.5">Skills</p>
                {view.skills.length === 0 ? (
                  <p className="text-[13px] text-muted-foreground">None used yet.</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {view.skills.map((skill) => (
                      <span
                        key={skill}
                        className="px-2 py-1 rounded-full border border-border bg-secondary/40 text-[12px] text-foreground"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </CollapsibleSection>
        </div>
      )}
    </aside>
  )
}
