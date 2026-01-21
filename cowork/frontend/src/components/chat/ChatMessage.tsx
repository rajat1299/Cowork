import { cn } from '../../lib/utils'
import type { Message } from '../../types/chat'

interface ChatMessageProps {
  message: Message
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'
  const isStreaming = message.isStreaming

  // System messages (errors, notices)
  if (isSystem) {
    return (
      <div className="flex justify-center">
        <div className="px-4 py-2 rounded-lg bg-dark-elevated text-ink-muted text-[13px] max-w-[85%]">
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
      <div
        className={cn(
          'max-w-[75%] px-4 py-3 rounded-2xl',
          isUser
            ? 'bg-burnt text-white rounded-br-md'
            : 'bg-dark-surface text-ink border border-dark-border rounded-bl-md'
        )}
      >
        <p className="text-[14px] leading-relaxed whitespace-pre-wrap">
          {message.content}
          {isStreaming && (
            <span className="inline-block w-2 h-4 ml-1 bg-ink-muted animate-pulse rounded-sm" />
          )}
        </p>
        {message.agentName && (
          <p className="mt-1 text-[11px] text-ink-subtle">
            via {message.agentName}
          </p>
        )}
      </div>
    </div>
  )
}
