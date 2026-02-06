import { useRef, useEffect, useCallback, useMemo, useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Download,
  Clipboard,
  Check,
  Loader2,
  AlertCircle,
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
import { ORCHESTRATOR_URL } from '../../api/client'
import { buildTurnExecutionView, type EvidenceBlock } from '../../lib/execution'
import { cn } from '../../lib/utils'
import type { ArtifactInfo } from '../../types/chat'

function resolveArtifactUrl(url?: string): string | undefined {
  if (!url) return undefined
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `${ORCHESTRATOR_URL}${url.startsWith('/') ? '' : '/'}${url}`
}

function EvidenceTimeline({ evidence }: { evidence: EvidenceBlock[] }) {
  const [open, setOpen] = useState<Record<string, boolean>>({})

  if (evidence.length === 0) return null

  return (
    <div className="space-y-2">
      {evidence.map((item) => {
        const expanded = open[item.id] || false
        return (
          <div key={item.id} className="rounded-lg border border-border/70 bg-secondary/30 overflow-hidden">
            <button
              onClick={() => setOpen((prev) => ({ ...prev, [item.id]: !expanded }))}
              className="w-full px-3 py-2 text-left flex items-center justify-between gap-3"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span
                  className={cn(
                    'w-5 h-5 rounded-full border flex items-center justify-center',
                    item.status === 'done' && 'bg-foreground/10 border-transparent',
                    item.status === 'running' && 'bg-burnt/10 border-burnt/40',
                    item.status === 'error' && 'bg-destructive/10 border-destructive/40'
                  )}
                >
                  {item.status === 'done' ? (
                    <Check size={12} className="text-foreground" />
                  ) : item.status === 'running' ? (
                    <Loader2 size={12} className="text-burnt animate-spin" />
                  ) : (
                    <AlertCircle size={12} className="text-destructive" />
                  )}
                </span>
                <span className="text-[13px] text-foreground truncate">{item.summary}</span>
              </div>
              {expanded ? (
                <ChevronDown size={14} className="text-muted-foreground" />
              ) : (
                <ChevronRight size={14} className="text-muted-foreground" />
              )}
            </button>

            {expanded ? (
              <div className="px-3 pb-3 pt-1 border-t border-border/60 space-y-2">
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
                    {item.searchResults.map((result, index) => (
                      <div
                        key={`${item.id}-result-${index}`}
                        className="rounded-md border border-border/60 bg-background/30 px-2.5 py-2"
                      >
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
                    ))}
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
      })}
    </div>
  )
}

function ArtifactCards({ artifacts }: { artifacts: ArtifactInfo[] }) {
  if (artifacts.length === 0) return null

  return (
    <div className="space-y-2">
      {artifacts.map((artifact) => {
        const url = resolveArtifactUrl(artifact.contentUrl)
        return (
          <div key={artifact.id} className="rounded-lg border border-border/70 bg-secondary/30 p-3">
            <p className="text-[13px] font-medium text-foreground truncate">{artifact.name}</p>
            {artifact.path ? (
              <p className="text-[11px] text-muted-foreground truncate mt-0.5">{artifact.path}</p>
            ) : null}

            <div className="mt-2 flex items-center gap-1.5">
              {url ? (
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-border text-[11px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
                >
                  <ExternalLink size={12} />
                  Open
                </a>
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
      })}
    </div>
  )
}

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

  const inlineArtifacts = useMemo(() => {
    const attached = new Set<string>()
    messages.forEach((message) => {
      message.artifacts?.forEach((artifact) => attached.add(artifact.id))
    })
    return artifacts.filter((artifact) => !attached.has(artifact.id))
  }, [artifacts, messages])
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
  }, [messages, isConnecting, isRunning, progressSteps])

  // Handle sending messages
  const handleSend = useCallback(
    async (content: string, options?: ChatMessageOptions) => {
      try {
        if (messages.length === 0) {
          // Start new conversation
          await sendMessage(content, options)
        } else {
          // Send follow-up
          await sendFollowUp(content, options)
        }
      } catch (err) {
        console.error('Failed to send message:', err)
      }
    },
    [messages.length, sendMessage, sendFollowUp]
  )

  // Handle stop
  const handleStop = useCallback(() => {
    stopTask()
  }, [stopTask])

  const isWelcome = messages.length === 0
  const isLoading = isConnecting || isRunning

  return (
    <div className="flex flex-col h-full">
      {/* Messages or Welcome Screen */}
      <div className="flex-1 overflow-y-auto">
        {isWelcome ? (
          <WelcomeScreen onPromptSelect={handleSend} />
        ) : (
          <div className="max-w-2xl mx-auto px-5 py-6 space-y-4">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}

            {executionView.evidence.length > 0 ? (
              <EvidenceTimeline evidence={executionView.evidence} />
            ) : null}

            {inlineArtifacts.length > 0 ? <ArtifactCards artifacts={inlineArtifacts.slice(-6)} /> : null}

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
