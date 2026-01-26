import { useState, useRef, useEffect } from 'react'
import { FolderOpen, Plus, ChevronDown, ArrowRight } from 'lucide-react'
import { cn } from '../../lib/utils'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  isWelcome?: boolean
}

export function ChatInput({ onSend, disabled = false, isWelcome = false }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`
    }
  }, [value])

  const handleSubmit = () => {
    const trimmed = value.trim()
    if (trimmed && !disabled) {
      onSend(trimmed)
      setValue('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  if (isWelcome) {
    return (
      <div className="space-y-3">
        {/* Main input */}
        <div className="relative bg-secondary rounded-2xl border border-border overflow-hidden">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="How can I help you today?"
            disabled={disabled}
            rows={1}
            className={cn(
              'w-full resize-none bg-transparent px-5 py-4',
              'text-[15px] text-foreground leading-relaxed',
              'placeholder:text-muted-foreground',
              'focus:outline-none',
              'disabled:opacity-50'
            )}
          />
        </div>

        {/* Bottom row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {/* Work in a folder button */}
            <button className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-lg',
              'text-[13px] text-muted-foreground',
              'hover:bg-secondary hover:text-foreground',
              'transition-all duration-200',
              'border border-transparent hover:border-border'
            )}>
              <FolderOpen size={16} strokeWidth={1.5} />
              <span>Work in a folder</span>
            </button>

            {/* Add attachment */}
            <button className={cn(
              'w-8 h-8 rounded-lg flex items-center justify-center',
              'text-muted-foreground hover:text-foreground hover:bg-secondary',
              'transition-all duration-200'
            )}>
              <Plus size={18} strokeWidth={1.5} />
            </button>
          </div>

          <div className="flex items-center gap-3">
            {/* Model selector */}
            <button className={cn(
              'flex items-center gap-1.5 px-3 py-2 rounded-lg',
              'text-[13px] text-muted-foreground',
              'hover:bg-secondary',
              'transition-all duration-200'
            )}>
              <span>Opus 4.5</span>
              <ChevronDown size={14} strokeWidth={1.5} />
            </button>

            {/* Let's go button */}
            <button
              onClick={handleSubmit}
              disabled={disabled}
              className={cn(
                'flex items-center gap-2 px-4 py-2.5 rounded-xl',
                'bg-foreground text-background',
                'text-[14px] font-medium',
                'hover:bg-foreground/90',
                'transition-all duration-200',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              <span>Let's go</span>
              <ArrowRight size={16} strokeWidth={2} />
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Standard chat input (non-welcome state)
  return (
    <div className="relative flex items-end gap-3 p-4 bg-secondary rounded-2xl border border-border">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Message..."
        disabled={disabled}
        rows={1}
        className={cn(
          'flex-1 resize-none bg-transparent py-1.5 px-1',
          'text-[14px] text-foreground leading-relaxed',
          'placeholder:text-muted-foreground',
          'focus:outline-none',
          'disabled:opacity-50'
        )}
      />

      <button
        type="button"
        onClick={handleSubmit}
        disabled={disabled || !value.trim()}
        className={cn(
          'w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0',
          'transition-all duration-200',
          value.trim() && !disabled
            ? 'bg-burnt text-white'
            : 'bg-accent text-muted-foreground'
        )}
      >
        <ArrowRight size={16} strokeWidth={2} />
      </button>
    </div>
  )
}
