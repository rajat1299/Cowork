import { memo } from 'react'
import { FileText, Image as ImageIcon } from 'lucide-react'
import { cn } from '../../lib/utils'
import type { Message, AttachmentInfo } from '../../types/chat'

interface ChatMessageProps {
  message: Message
}

export const ChatMessage = memo(function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'
  const isStreaming = message.isStreaming
  const attachments = message.attachments || []

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
    <div
      className={cn(
        'flex',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      <div className="max-w-[75%]">
        {attachments.length > 0 && (
          <AttachmentGrid attachments={attachments} alignRight={isUser} />
        )}
        <div
          className={cn(
            'px-4 py-3 rounded-2xl',
            isUser
              ? 'bg-burnt text-white rounded-br-md'
              : 'bg-secondary text-foreground border border-border rounded-bl-md'
          )}
        >
          <p className="text-[14px] leading-relaxed whitespace-pre-wrap">
            {message.content}
            {isStreaming && (
              <span className="inline-block w-2 h-4 ml-1 bg-muted-foreground animate-pulse rounded-sm" />
            )}
          </p>
          {message.agentName && (
            <p className="mt-1 text-[11px] text-muted-foreground">
              via {message.agentName}
            </p>
          )}
        </div>
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
    <div
      className={cn(
        'mb-2 flex flex-wrap gap-2',
        alignRight ? 'justify-end' : 'justify-start'
      )}
    >
      {attachments.map((attachment) => {
        const isImage = attachment.kind === 'image' || attachment.contentType?.startsWith('image/')
        const previewUrl = attachment.previewUrl || attachment.url
        return (
          <div
            key={attachment.id}
            className={cn(
              'w-28 rounded-xl border border-border overflow-hidden',
              'bg-secondary/70'
            )}
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
