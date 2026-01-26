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
      <div
        className={cn(
          'max-w-[75%] px-4 py-3 rounded-2xl',
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
  )
}
