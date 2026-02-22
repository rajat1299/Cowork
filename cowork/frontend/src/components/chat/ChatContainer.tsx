import { useRef, useEffect, useCallback, useMemo, useState, memo } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Check,
  Loader2,
  AlertCircle,
  ExternalLink,
  Download,
  Clipboard,
  Share2,
  CheckCircle2,
} from 'lucide-react'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { TypingIndicator } from './TypingIndicator'
import { WelcomeScreen } from './WelcomeScreen'
import { CompactingNotice } from './CompactingNotice'
import { useChat } from '../../hooks'
import type { ChatMessageOptions } from '../../hooks/useChat'
import { useChatStore } from '../../stores/chatStore'
import { StopCircle } from 'lucide-react'
import { buildTurnExecutionView, type EvidenceBlock } from '../../lib/execution'
import {
  artifactFamilyKey,
  canPreviewArtifact,
  dedupeArtifactsByCanonicalName,
  filterUserArtifacts,
  resolveArtifactUrl,
} from '../../lib/artifacts'
import { cn } from '../../lib/utils'
import { useViewerStore } from '../../stores/viewerStore'
import { share as shareApi } from '../../api/coreApi'
import type { ArtifactInfo, Message } from '../../types/chat'

type TimelineItem =
  | { kind: 'message'; id: string; timestamp: number; order: number; message: Message }
  | { kind: 'evidence'; id: string; timestamp: number; order: number; evidence: EvidenceBlock }
  | { kind: 'artifact'; id: string; timestamp: number; order: number; artifact: ArtifactInfo }

const EvidenceRow = memo(function EvidenceRow({ item }: { item: EvidenceBlock }) {
  const [expanded, setExpanded] = useState(false)

  const statusIcon =
    item.status === 'done' ? (
      <Check size={12} className="text-foreground" />
    ) : item.status === 'running' ? (
      <Loader2 size={12} className="text-burnt animate-spin" />
    ) : (
      <AlertCircle size={12} className="text-destructive" />
    )

  return (
    <div className="ml-1 rounded-md border border-border/55 bg-secondary/15 overflow-hidden animate-fade-in">
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full px-2.5 py-2 text-left flex items-center justify-between gap-2"
      >
        <div className="min-w-0 flex items-center gap-2">
          <span
            className={cn(
              'w-4 h-4 rounded-full border flex items-center justify-center',
              item.status === 'done' && 'bg-foreground/10 border-transparent',
              item.status === 'running' && 'bg-burnt/10 border-burnt/40',
              item.status === 'error' && 'bg-destructive/10 border-destructive/40'
            )}
          >
            {statusIcon}
          </span>
          <span className="text-[13px] text-muted-foreground truncate">{item.summary}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {item.searchResults?.length ? (
            <span className="text-[11px] text-muted-foreground/80">{item.searchResults.length} results</span>
          ) : null}
          {expanded ? (
            <ChevronDown size={14} className="text-muted-foreground" />
          ) : (
            <ChevronRight size={14} className="text-muted-foreground" />
          )}
        </div>
      </button>

      {expanded ? (
        <div className="px-2.5 pb-2.5 pt-1 border-t border-border/50 space-y-2">
          {item.request ? (
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">Request</p>
              <pre className="text-[12px] text-muted-foreground whitespace-pre-wrap break-words bg-background/40 rounded-md p-2 border border-border/60">
                {item.request}
              </pre>
            </div>
          ) : null}

          {item.searchResults && item.searchResults.length > 0 ? (
            <div className="space-y-1.5">
              {item.searchResults.map((result, index) => {
                const faviconHost = result.domain || result.url || ''
                const faviconUrl = faviconHost
                  ? `https://www.google.com/s2/favicons?sz=32&domain_url=${encodeURIComponent(faviconHost)}`
                  : undefined
                return (
                  <div
                    key={`${item.id}-result-${index}`}
                    className="rounded-md border border-border/60 bg-background/30 px-2.5 py-2"
                  >
                    <div className="flex items-start gap-2">
                      {faviconUrl ? (
                        <img
                          src={faviconUrl}
                          alt=""
                          className="w-4 h-4 mt-0.5 rounded-sm shrink-0"
                          loading="lazy"
                        />
                      ) : null}
                      <div className="min-w-0">
                        {result.url ? (
                          <a
                            href={result.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[12px] text-foreground hover:underline break-words"
                          >
                            {result.title}
                          </a>
                        ) : (
                          <p className="text-[12px] text-foreground break-words">{result.title}</p>
                        )}
                        {result.domain ? (
                          <p className="text-[11px] text-muted-foreground mt-0.5">{result.domain}</p>
                        ) : null}
                        {result.error ? (
                          <p className="text-[11px] text-destructive mt-0.5">{result.error}</p>
                        ) : null}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : item.result ? (
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">Result</p>
              <pre className="text-[12px] text-muted-foreground whitespace-pre-wrap break-words bg-background/40 rounded-md p-2 border border-border/60">
                {item.result}
              </pre>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
})

const InlineArtifactCard = memo(function InlineArtifactCard({ artifact }: { artifact: ArtifactInfo }) {
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
    <div className="rounded-lg border border-border/70 bg-secondary/25 p-3 animate-fade-in">
      <p className="text-[13px] font-medium text-foreground truncate">{artifact.name}</p>
      {artifact.path ? <p className="text-[11px] text-muted-foreground truncate mt-0.5">{artifact.path}</p> : null}

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
})

export function ChatContainer() {
  const {
    messages,
    isConnecting,
    isRunning,
    error,
    sendMessage,
    sendFollowUp,
    stopTask,
    progressSteps,
    artifacts,
  } = useChat()

  const executionView = useMemo(() => buildTurnExecutionView(progressSteps), [progressSteps])

  const timeline = useMemo(() => {
    const attachedArtifactKeys = new Set<string>()
    const fallbackBaseTimestamp =
      executionView.turnSteps[0]?.timestamp ||
      messages[messages.length - 1]?.timestamp ||
      0
    messages.forEach((message) => {
      dedupeArtifactsByCanonicalName(filterUserArtifacts(message.artifacts || [])).forEach((artifact) => {
        attachedArtifactKeys.add(artifactFamilyKey(artifact))
      })
    })

    const items: TimelineItem[] = []

    messages.forEach((message, index) => {
      items.push({
        kind: 'message',
        id: message.id,
        timestamp: message.timestamp || 0,
        order: index,
        message,
      })
    })

    executionView.evidence.forEach((evidence, index) => {
      items.push({
        kind: 'evidence',
        id: evidence.id,
        timestamp: evidence.timestamp || fallbackBaseTimestamp + index + 1,
        order: 1000 + index,
        evidence,
      })
    })

    dedupeArtifactsByCanonicalName(artifacts)
      .filter((artifact) => !attachedArtifactKeys.has(artifactFamilyKey(artifact)))
      .forEach((artifact, index) => {
        items.push({
          kind: 'artifact',
          id: artifact.id,
          timestamp: artifact.createdAt || fallbackBaseTimestamp + 1000 + index,
          order: 2000 + index,
          artifact,
        })
      })

    items.sort((a, b) => {
      if (a.timestamp !== b.timestamp) return a.timestamp - b.timestamp
      return a.order - b.order
    })

    return items
  }, [artifacts, executionView.evidence, executionView.turnSteps, messages])

  const hasStreamingAssistant = useMemo(
    () => messages.some((message) => message.role === 'assistant' && message.isStreaming),
    [messages]
  )

  // Get notice from active task - use stable selector to avoid re-renders
  const activeTaskNotice = useChatStore((s) => {
    const taskId = s.activeTaskId
    return taskId ? s.tasks[taskId]?.notice ?? null : null
  })

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isConnecting, isRunning, progressSteps, timeline.length])

  // Read activeProjectId to decide new-chat vs follow-up routing
  const activeProjectId = useChatStore((s) => s.activeProjectId)

  // Handle sending messages
  const handleSend = useCallback(
    async (content: string, options?: ChatMessageOptions) => {
      try {
        if (!activeProjectId) {
          // No active project — truly a new chat
          await sendMessage(content, options)
        } else {
          // Active project exists — continue the conversation
          await sendFollowUp(content, options)
        }
      } catch (err) {
        console.error('Failed to send message:', err)
      }
    },
    [activeProjectId, sendMessage, sendFollowUp]
  )

  // Handle stop
  const handleStop = useCallback(() => {
    stopTask()
  }, [stopTask])

  const isWelcome = messages.length === 0
  const isLoading = isConnecting || isRunning

  // Share state
  const [shareState, setShareState] = useState<'idle' | 'loading' | 'copied'>('idle')
  const activeTaskId = useChatStore((s) => s.activeTaskId)

  const handleShare = useCallback(async () => {
    if (!activeTaskId || shareState === 'loading') return
    setShareState('loading')
    try {
      const result = await shareApi.create(activeTaskId)
      const shareUrl = `${window.location.origin}/share/${result.token}`
      await navigator.clipboard.writeText(shareUrl)
      setShareState('copied')
      setTimeout(() => setShareState('idle'), 2000)
    } catch {
      setShareState('idle')
    }
  }, [activeTaskId, shareState])

  return (
    <div className="flex flex-col h-full">
      {/* Messages or Welcome Screen */}
      <div className="flex-1 overflow-y-auto">
        {isWelcome ? (
          <WelcomeScreen onPromptSelect={handleSend} />
        ) : (
          <div className="max-w-2xl mx-auto px-5 py-6 space-y-4">
            {/* Share button */}
            <div className="flex justify-end -mb-2">
              <button
                onClick={handleShare}
                disabled={shareState === 'loading'}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg',
                  'text-[12px] text-muted-foreground',
                  'hover:text-foreground hover:bg-secondary',
                  'transition-colors',
                  shareState === 'copied' && 'text-green-500'
                )}
              >
                {shareState === 'loading' ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : shareState === 'copied' ? (
                  <CheckCircle2 size={14} />
                ) : (
                  <Share2 size={14} />
                )}
                {shareState === 'copied' ? 'Link copied!' : 'Share'}
              </button>
            </div>
            {timeline.map((item) => {
              if (item.kind === 'message') {
                return <ChatMessage key={item.id} message={item.message} />
              }
              if (item.kind === 'evidence') {
                return <EvidenceRow key={item.id} item={item.evidence} />
              }
              return <InlineArtifactCard key={item.id} artifact={item.artifact} />
            })}

            {/* Compacting notice when backend is summarizing history */}
            {activeTaskNotice && (
              <CompactingNotice
                message={activeTaskNotice.message}
                progress={activeTaskNotice.progress}
              />
            )}

            {/* Typing indicator while loading */}
            {isLoading && !activeTaskNotice && !hasStreamingAssistant && <TypingIndicator />}

            {/* Error message */}
            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-[13px]">
                {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Stop button when running */}
      {isRunning && (
        <div className="flex justify-center py-2">
          <button
            onClick={handleStop}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg',
              'bg-secondary border border-border',
              'text-muted-foreground hover:text-foreground hover:border-foreground/30',
              'transition-colors text-[13px]'
            )}
          >
            <StopCircle size={16} />
            Stop generating
          </button>
        </div>
      )}

      {/* Input */}
      <div className="px-5 pb-5 pt-2">
        <div className={isWelcome ? 'max-w-[600px] mx-auto' : 'max-w-2xl mx-auto'}>
          <ChatInput
            onSend={handleSend}
            disabled={isConnecting}
            isWelcome={isWelcome}
          />
        </div>
      </div>
    </div>
  )
}
