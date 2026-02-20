import { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { FileText, Image as ImageIcon, ExternalLink, Download, Clipboard } from 'lucide-react'
import { canPreviewArtifact, dedupeArtifactsByCanonicalName, filterUserArtifacts, resolveArtifactUrl } from '../../lib/artifacts'
import { cn } from '../../lib/utils'
import { useViewerStore } from '../../stores/viewerStore'
import type { Message, AttachmentInfo, ArtifactInfo } from '../../types/chat'

interface ChatMessageProps {
  message: Message
}

const ArtifactCard = memo(function ArtifactCard({ artifact }: { artifact: ArtifactInfo }) {
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

export const ChatMessage = memo(function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'
  const isStreaming = message.isStreaming
  const attachments = message.attachments || []
  const artifacts = dedupeArtifactsByCanonicalName(filterUserArtifacts(message.artifacts || []))
  const hasContent = message.content.trim().length > 0

  // System messages (errors, notices)
  if (isSystem) {
    return (
      <div className="flex justify-center">
        <div className="px-4 py-2 rounded-lg bg-accent text-muted-foreground text-[13px] max-w-[85%]">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div className={cn('space-y-2', isUser ? 'max-w-[75%]' : 'max-w-[90%]')}>
        {attachments.length > 0 && <AttachmentGrid attachments={attachments} alignRight={isUser} />}

        {hasContent ? (
          <div
            className={cn(
              isUser
                ? 'px-4 py-3 rounded-2xl bg-burnt text-white rounded-br-md'
                : 'px-0 py-0 text-foreground'
            )}
          >
            {isUser ? (
              <p className="text-[14px] leading-relaxed whitespace-pre-wrap">
                {message.content}
                {isStreaming ? (
                  <span className="inline-block w-2 h-4 ml-1 bg-white/80 animate-pulse rounded-sm" />
                ) : null}
              </p>
            ) : (
              <div className="max-w-none text-[15px] leading-7">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="my-3 text-[15px] leading-7 text-foreground">{children}</p>,
                    h1: ({ children }) => <h1 className="mt-5 mb-3 text-[30px] font-semibold tracking-tight">{children}</h1>,
                    h2: ({ children }) => <h2 className="mt-5 mb-2 text-[24px] font-semibold tracking-tight">{children}</h2>,
                    h3: ({ children }) => <h3 className="mt-4 mb-2 text-[19px] font-semibold">{children}</h3>,
                    ul: ({ children }) => <ul className="my-3 list-disc pl-5 space-y-1.5">{children}</ul>,
                    ol: ({ children }) => <ol className="my-3 list-decimal pl-5 space-y-1.5">{children}</ol>,
                    li: ({ children }) => <li className="text-[15px] leading-7">{children}</li>,
                    blockquote: ({ children }) => (
                      <blockquote className="my-3 border-l-2 border-border pl-3 text-muted-foreground">{children}</blockquote>
                    ),
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noreferrer" className="text-foreground underline decoration-muted-foreground/40 hover:decoration-foreground">
                        {children}
                      </a>
                    ),
                    code: ({ className, children }) => {
                      const isBlock = Boolean(className)
                      if (isBlock) {
                        return (
                          <code className="block my-3 p-3 rounded-lg border border-border bg-secondary/40 overflow-x-auto text-[13px] leading-6 text-muted-foreground">
                            {children}
                          </code>
                        )
                      }
                      return (
                        <code className="px-1.5 py-0.5 rounded bg-secondary/60 border border-border text-[13px]">
                          {children}
                        </code>
                      )
                    },
                    pre: ({ children }) => <pre className="m-0">{children}</pre>,
                    table: ({ children }) => (
                      <div className="my-3 overflow-x-auto">
                        <table className="w-full border-collapse text-[13px]">{children}</table>
                      </div>
                    ),
                    thead: ({ children }) => <thead className="bg-secondary/40">{children}</thead>,
                    tbody: ({ children }) => <tbody>{children}</tbody>,
                    tr: ({ children }) => <tr className="border-b border-border/60">{children}</tr>,
                    th: ({ children }) => <th className="px-2 py-1.5 text-left font-semibold">{children}</th>,
                    td: ({ children }) => <td className="px-2 py-1.5 text-muted-foreground">{children}</td>,
                  }}
                >
                  {message.content}
                </ReactMarkdown>
                {isStreaming ? (
                  <span className="inline-block w-2 h-4 ml-1 bg-muted-foreground animate-pulse rounded-sm align-middle" />
                ) : null}
              </div>
            )}

            {message.agentName && !isUser ? (
              <p className="mt-1 text-[11px] text-muted-foreground">via {message.agentName}</p>
            ) : null}
          </div>
        ) : null}

        {artifacts.length > 0 ? (
          <div className="space-y-2">
            {artifacts.map((artifact) => (
              <ArtifactCard key={artifact.id} artifact={artifact} />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
})

function AttachmentGrid({
  attachments,
  alignRight,
}: {
  attachments: AttachmentInfo[]
  alignRight: boolean
}) {
  return (
    <div className={cn('mb-2 flex flex-wrap gap-2', alignRight ? 'justify-end' : 'justify-start')}>
      {attachments.map((attachment) => {
        const isImage = attachment.kind === 'image' || attachment.contentType?.startsWith('image/')
        const previewUrl = attachment.previewUrl || attachment.url
        return (
          <div
            key={attachment.id}
            className={cn('w-28 rounded-xl border border-border overflow-hidden', 'bg-secondary/70')}
          >
            {isImage && previewUrl ? (
              <img
                src={previewUrl}
                alt={attachment.name}
                className="w-full h-20 object-cover"
              />
            ) : (
              <div className="w-full h-20 flex items-center justify-center text-muted-foreground">
                {isImage ? <ImageIcon size={18} /> : <FileText size={18} />}
              </div>
            )}
            <div className="px-2 py-1 text-[11px] text-muted-foreground truncate">
              {attachment.name}
            </div>
          </div>
        )
      })}
    </div>
  )
}
