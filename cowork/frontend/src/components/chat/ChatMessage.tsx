import { cn } from '../../lib/utils'
import type { Message } from '../../types/chat'

interface ChatMessageProps {
  message: Message
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'

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
        <p className="text-[14px] leading-relaxed whitespace-pre-wrap">{message.content}</p>
      </div>
    </div>
  )
}
