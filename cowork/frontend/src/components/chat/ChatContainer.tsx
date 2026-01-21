import { useRef, useEffect, useCallback } from 'react'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { TypingIndicator } from './TypingIndicator'
import { WelcomeScreen } from './WelcomeScreen'
import { useChat } from '../../hooks'
import { StopCircle } from 'lucide-react'
import { cn } from '../../lib/utils'

export function ChatContainer() {
  const {
    messages,
    isConnecting,
    isRunning,
    error,
    sendMessage,
    sendFollowUp,
    stopTask,
  } = useChat()

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isConnecting, isRunning])

  // Handle sending messages
  const handleSend = useCallback(
    async (content: string) => {
      try {
        if (messages.length === 0) {
          // Start new conversation
          await sendMessage(content)
        } else {
          // Send follow-up
          await sendFollowUp(content)
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

            {/* Typing indicator while loading */}
            {isLoading && <TypingIndicator />}

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
              'bg-dark-surface border border-dark-border',
              'text-ink-muted hover:text-ink hover:border-ink-faint',
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
