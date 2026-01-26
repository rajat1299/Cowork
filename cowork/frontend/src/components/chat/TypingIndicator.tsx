import { useMemo, useState, useEffect } from 'react'
import { useChatStore } from '../../stores/chatStore'
import { Sparkles } from 'lucide-react'

/**
 * Fun pre-response messages shown while waiting for LLM
 */
const PONDERING_MESSAGES = [
  'Pondering...',
  'Thinking it through...',
  'Brewing some ideas...',
  'Connecting the dots...',
  'Working on it...',
  'Almost there...',
]

/**
 * Map step types to human-friendly status messages
 */
function getStatusMessage(step: string | null, isDecomposing: boolean): string {
  if (!step && !isDecomposing) {
    // No step yet - show fun waiting message
    return PONDERING_MESSAGES[Math.floor(Math.random() * PONDERING_MESSAGES.length)]
  }
  
  if (isDecomposing) return 'Breaking down your request...'
  
  switch (step) {
    case 'confirmed': return 'Got it, starting now...'
    case 'decompose_text': return 'Analyzing what needs to be done...'
    case 'to_sub_tasks': return 'Planning the approach...'
    case 'create_agent': return 'Setting up the right tools...'
    case 'activate_agent': return 'Getting to work...'
    case 'assign_task': return 'Delegating tasks...'
    case 'activate_toolkit': return 'Using tools...'
    case 'deactivate_toolkit': return 'Tool finished...'
    case 'streaming': return 'Writing response...'
    case 'artifact': return 'Creating output...'
    case 'write_file': return 'Writing file...'
    default: return 'Working on it...'
  }
}

export function TypingIndicator() {
  const activeTaskId = useChatStore((s) => s.activeTaskId)
  const tasks = useChatStore((s) => s.tasks)
  
  const task = activeTaskId ? tasks[activeTaskId] : null
  const currentStep = task?.currentStep ?? null
  const isDecomposing = Boolean(task?.streamingDecomposeText)
  
  // Rotate pondering messages every 2s when no step yet
  const [messageIndex, setMessageIndex] = useState(0)
  
  useEffect(() => {
    if (!currentStep && !isDecomposing) {
      const interval = setInterval(() => {
        setMessageIndex((i) => (i + 1) % PONDERING_MESSAGES.length)
      }, 2000)
      return () => clearInterval(interval)
    }
  }, [currentStep, isDecomposing])
  
  const statusMessage = useMemo(() => {
    if (!currentStep && !isDecomposing) {
      return PONDERING_MESSAGES[messageIndex]
    }
    return getStatusMessage(currentStep, isDecomposing)
  }, [currentStep, isDecomposing, messageIndex])

  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2.5 px-4 py-3">
        {/* Animated sparkle icon */}
        <Sparkles 
          size={16} 
          className="text-burnt animate-pulse" 
        />
        
        {/* Status text */}
        <span className="text-[13px] text-muted-foreground animate-fade-in">
          {statusMessage}
        </span>
      </div>
    </div>
  )
}
