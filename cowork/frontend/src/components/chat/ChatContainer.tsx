import { useRef, useEffect, useCallback } from 'react'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { TypingIndicator } from './TypingIndicator'
import { WelcomeScreen } from './WelcomeScreen'
import { CompactingNotice } from './CompactingNotice'
import { WorkFlowPanel } from '../WorkFlow'
import { useChat, useWorkflow } from '../../hooks'
import type { ChatMessageOptions } from '../../hooks/useChat'
import { useChatStore } from '../../stores/chatStore'
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

  // Workflow state for the panel
  const {
    agents,
    tasks,
    activeAgentId,
    decomposeText,
    status: workflowStatus,
  } = useWorkflow()

  // Get notice from active task - use stable selector to avoid re-renders
  const activeTaskNotice = useChatStore((s) => {
    const taskId = s.activeTaskId
    return taskId ? s.tasks[taskId]?.notice ?? null : null
  })

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isConnecting, isRunning])

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
      {/* Workflow Panel - shows when task is running */}
      <WorkFlowPanel
        agents={agents}
        tasks={tasks}
        activeAgentId={activeAgentId}
        decomposeText={decomposeText}
        status={workflowStatus}
        isVisible={workflowStatus !== 'idle'}
      />

      {/* Messages or Welcome Screen */}
      <div className="flex-1 overflow-y-auto">
        {isWelcome ? (
          <WelcomeScreen onPromptSelect={handleSend} />
        ) : (
          <div className="max-w-2xl mx-auto px-5 py-6 space-y-4">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}

            {/* Compacting notice when backend is summarizing history */}
            {activeTaskNotice && (
              <CompactingNotice
                message={activeTaskNotice.message}
                progress={activeTaskNotice.progress}
              />
            )}

            {/* Typing indicator while loading */}
            {isLoading && !activeTaskNotice && <TypingIndicator />}

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
