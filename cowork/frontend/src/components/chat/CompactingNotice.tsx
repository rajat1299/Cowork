import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/utils'

interface CompactingNoticeProps {
  message?: string
  progress?: number
  className?: string
}

/**
 * Notice displayed when the backend is compacting conversation history
 * Shown inline in the chat area without a message bubble
 */
export function CompactingNotice({
  message = 'Compacting our conversation so we can keep chatting...',
  progress,
  className,
}: CompactingNoticeProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-8 px-4',
        'animate-fade-in',
        className
      )}
    >
      <div className="flex items-center gap-3 mb-3">
        {/* Animated spinner */}
        <div className="relative">
          <Loader2
            size={24}
            className="text-burnt animate-spin"
            strokeWidth={2}
          />
        </div>

        {/* Message text */}
        <p className="text-[15px] text-muted-foreground italic">{message}</p>
      </div>

      {/* Progress bar (optional) */}
      {progress !== undefined && (
        <div className="w-64 flex items-center gap-3">
          <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-foreground rounded-full transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-[13px] text-muted-foreground font-medium min-w-[40px]">
            {progress}%
          </span>
        </div>
      )}
    </div>
  )
}

export default CompactingNotice
