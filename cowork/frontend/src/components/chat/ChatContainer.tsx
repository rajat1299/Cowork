import { useState, useRef, useEffect } from 'react'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { TypingIndicator } from './TypingIndicator'
import { WelcomeScreen } from './WelcomeScreen'
import type { Message } from '../../types/chat'

const generateId = () => Math.random().toString(36).substring(2, 15)

export function ChatContainer() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSend = async (content: string) => {
    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    setTimeout(() => {
      const assistantMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: `${content}\n\nThis is a placeholder. Connect your backend for real responses.`,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, assistantMessage])
      setIsLoading(false)
    }, 1200)
  }

  const isWelcome = messages.length === 0

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
            {isLoading && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-5 pb-5 pt-2">
        <div className={isWelcome ? 'max-w-[600px] mx-auto' : 'max-w-2xl mx-auto'}>
          <ChatInput onSend={handleSend} disabled={isLoading} isWelcome={isWelcome} />
        </div>
      </div>
    </div>
  )
}
