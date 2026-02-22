import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import {
  Check,
  CornerDownLeft,
  GripVertical,
  Loader2,
  PencilLine,
  Sparkles,
  X,
} from 'lucide-react'
import { permission } from '../../api/orchestrator'
import { cn } from '../../lib/utils'
import { useChatStore } from '../../stores/chatStore'
import { createMessage } from '../../types/chat'
import type { DecisionData } from '../../types/chat'

interface DecisionWidgetProps {
  decision: DecisionData
}

const KEYBOARD_HINT_TEXT = '\u2191\u2193 to navigate \u00b7 Enter to select \u00b7 Esc to skip'

function reorderIds(ids: string[], draggedId: string, targetId: string): string[] {
  if (draggedId === targetId) return ids
  const fromIndex = ids.indexOf(draggedId)
  const toIndex = ids.indexOf(targetId)
  if (fromIndex < 0 || toIndex < 0) return ids

  const next = [...ids]
  const [moved] = next.splice(fromIndex, 1)
  next.splice(toIndex, 0, moved)
  return next
}

export const DecisionWidget = memo(function DecisionWidget({ decision }: DecisionWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const freeformInputRef = useRef<HTMLInputElement>(null)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeIndex, setActiveIndex] = useState(0)
  const [selectedSingleId, setSelectedSingleId] = useState<string | null>(
    () => decision.options[0]?.id || null
  )
  const [selectedMultiIds, setSelectedMultiIds] = useState<string[]>([])
  const [rankedIds, setRankedIds] = useState<string[]>(() =>
    decision.options.map((option) => option.id)
  )
  const [draggedId, setDraggedId] = useState<string | null>(null)
  const [freeformValue, setFreeformValue] = useState('')

  const optionMap = useMemo(() => {
    return new Map(decision.options.map((option) => [option.id, option]))
  }, [decision.options])

  const rankedOptions = useMemo(() => {
    if (decision.mode !== 'rank') return decision.options
    return rankedIds
      .map((id) => optionMap.get(id))
      .filter((option): option is NonNullable<typeof option> => Boolean(option))
  }, [decision.mode, decision.options, optionMap, rankedIds])

  useEffect(() => {
    // Keep keyboard navigation active by default for this floating widget.
    requestAnimationFrame(() => {
      containerRef.current?.focus()
    })
  }, [decision.requestId])

  const submit = useCallback(
    async (response: string, userMessage: string) => {
      if (isSubmitting) return

      setIsSubmitting(true)
      setError(null)

      try {
        await permission.submitDecision(decision.projectId, decision.requestId, response)

        const store = useChatStore.getState()
        const activeTaskId = store.activeTaskId
        if (activeTaskId && userMessage.trim()) {
          store.addMessage(activeTaskId, createMessage('user', userMessage.trim()))
        }
        store.setDecision(null)
      } catch (err) {
        console.error('Failed to submit decision response:', err)
        setError('Failed to submit. Please try again.')
        setIsSubmitting(false)
      }
    },
    [decision.projectId, decision.requestId, isSubmitting]
  )

  const getSingleSelectResponse = useCallback(() => {
    const selectedId = selectedSingleId || decision.options[activeIndex]?.id || null
    if (!selectedId) return null
    const option = optionMap.get(selectedId)
    return {
      response: selectedId,
      userMessage: option?.label || selectedId,
    }
  }, [activeIndex, decision.options, optionMap, selectedSingleId])

  const getMultiSelectResponse = useCallback(() => {
    if (selectedMultiIds.length === 0) return null
    const labels = selectedMultiIds
      .map((id) => optionMap.get(id)?.label || id)
      .join(', ')
    return {
      response: selectedMultiIds.join(','),
      userMessage: labels,
    }
  }, [optionMap, selectedMultiIds])

  const getRankResponse = useCallback(() => {
    if (rankedIds.length === 0) return null
    const labels = rankedIds.map((id) => optionMap.get(id)?.label || id).join(' > ')
    return {
      response: rankedIds.join('>'),
      userMessage: labels,
    }
  }, [optionMap, rankedIds])

  const submitCurrentSelection = useCallback(async () => {
    const freeform = freeformValue.trim()
    if (freeform) {
      await submit(freeform, freeform)
      return
    }

    if (decision.mode === 'single_select') {
      const payload = getSingleSelectResponse()
      if (payload) {
        await submit(payload.response, payload.userMessage)
      }
      return
    }

    if (decision.mode === 'multi_select') {
      const payload = getMultiSelectResponse()
      if (payload) {
        await submit(payload.response, payload.userMessage)
      }
      return
    }

    if (decision.mode === 'rank') {
      const payload = getRankResponse()
      if (payload) {
        await submit(payload.response, payload.userMessage)
      }
    }
  }, [
    decision.mode,
    freeformValue,
    getMultiSelectResponse,
    getRankResponse,
    getSingleSelectResponse,
    submit,
  ])

  const handleSkip = useCallback(async () => {
    if (isSubmitting) return
    if (!decision.skippable) return
    await submit('skip', 'Skip')
  }, [decision.skippable, isSubmitting, submit])

  const handleMove = useCallback(
    (delta: number) => {
      const count = decision.options.length
      if (count === 0) return

      setActiveIndex((prev) => {
        const next = (prev + delta + count) % count
        if (decision.mode === 'single_select') {
          setSelectedSingleId(decision.options[next]?.id || null)
        }
        return next
      })
    },
    [decision.mode, decision.options]
  )

  const onContainerKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (isSubmitting) return

      const target = event.target as HTMLElement
      const isTypingInFreeform = target === freeformInputRef.current

      if (isTypingInFreeform && event.key === 'Enter') {
        event.preventDefault()
        void submitCurrentSelection()
        return
      }

      if (isTypingInFreeform && event.key !== 'Escape') {
        return
      }

      if (event.key === 'ArrowDown') {
        event.preventDefault()
        handleMove(1)
        return
      }

      if (event.key === 'ArrowUp') {
        event.preventDefault()
        handleMove(-1)
        return
      }

      if (event.key === 'Enter') {
        event.preventDefault()
        void submitCurrentSelection()
        return
      }

      if (event.key === 'Escape') {
        event.preventDefault()
        void handleSkip()
        return
      }

      if (decision.mode === 'single_select' && /^[1-9]$/.test(event.key)) {
        const index = Number(event.key) - 1
        const option = decision.options[index]
        if (!option) return
        event.preventDefault()
        setActiveIndex(index)
        setSelectedSingleId(option.id)
      }
    },
    [decision.mode, decision.options, handleMove, handleSkip, isSubmitting, submitCurrentSelection]
  )

  const handleSingleRowClick = useCallback(
    (index: number, optionId: string) => {
      setActiveIndex(index)
      setSelectedSingleId(optionId)
      containerRef.current?.focus()
    },
    []
  )

  const handleMultiToggle = useCallback((index: number, optionId: string) => {
    setActiveIndex(index)
    setSelectedMultiIds((prev) =>
      prev.includes(optionId) ? prev.filter((id) => id !== optionId) : [...prev, optionId]
    )
    containerRef.current?.focus()
  }, [])

  const handleRankDragStart = useCallback((optionId: string) => {
    setDraggedId(optionId)
  }, [])

  const handleRankDrop = useCallback((targetId: string) => {
    if (!draggedId) return
    setRankedIds((prev) => reorderIds(prev, draggedId, targetId))
    setDraggedId(null)
    containerRef.current?.focus()
  }, [draggedId])

  return (
    <div className="mb-3 animate-slide-up">
      <div
        ref={containerRef}
        tabIndex={0}
        onKeyDown={onContainerKeyDown}
        className={cn(
          'relative overflow-hidden rounded-[22px] border border-border/70',
          'bg-card/95 shadow-[0_18px_48px_rgba(0,0,0,0.18)]',
          'outline-none backdrop-blur-sm',
          'focus-visible:ring-2 focus-visible:ring-ring/30'
        )}
      >
        <Sparkles
          size={16}
          className="absolute -top-2.5 left-5 text-burnt/80 rotate-[-12deg]"
          aria-hidden="true"
        />

        <div className="flex items-start justify-between gap-3 px-5 py-4">
          <h3 className="text-[15px] leading-tight font-medium text-foreground">
            {decision.question}
          </h3>
          <button
            type="button"
            onClick={() => void handleSkip()}
            disabled={isSubmitting || !decision.skippable}
            className={cn(
              'mt-0.5 rounded-md p-1 text-muted-foreground transition-colors',
              'hover:bg-secondary hover:text-foreground',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
            aria-label={decision.skippable ? 'Skip decision' : 'Dismiss decision'}
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-3 pb-2">
          <div className="overflow-hidden rounded-xl border border-border/60 bg-background/30">
            {(decision.mode === 'rank' ? rankedOptions : decision.options).map((option, index) => {
              const isSingle = decision.mode === 'single_select'
              const isMulti = decision.mode === 'multi_select'
              const isRank = decision.mode === 'rank'
              const isActive = activeIndex === index
              const isSelectedSingle = selectedSingleId === option.id
              const isSelectedMulti = selectedMultiIds.includes(option.id)
              const isSelected = isSingle ? isSelectedSingle : isMulti ? isSelectedMulti : isActive

              return (
                <div
                  key={option.id}
                  className={cn(
                    index > 0 && 'border-t border-border/50'
                  )}
                >
                  <button
                    type="button"
                    onClick={() => {
                      if (isSingle) {
                        handleSingleRowClick(index, option.id)
                        return
                      }
                      if (isMulti) {
                        handleMultiToggle(index, option.id)
                        return
                      }
                      setActiveIndex(index)
                    }}
                    draggable={isRank}
                    onDragStart={() => handleRankDragStart(option.id)}
                    onDragOver={(event) => {
                      if (!isRank) return
                      event.preventDefault()
                    }}
                    onDrop={() => {
                      if (!isRank) return
                      handleRankDrop(option.id)
                    }}
                    className={cn(
                      'group flex w-full items-center gap-3 px-3 py-3 text-left transition-colors',
                      isSelected ? 'bg-muted/65' : 'hover:bg-muted/35'
                    )}
                  >
                    {isRank ? (
                      <span className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-muted/75 text-muted-foreground">
                        <GripVertical size={14} />
                      </span>
                    ) : (
                      <span
                        className={cn(
                          'inline-flex h-8 w-8 items-center justify-center rounded-xl text-[14px] font-medium',
                          isSelected
                            ? 'bg-background/70 text-foreground'
                            : 'bg-muted/80 text-muted-foreground'
                        )}
                      >
                        {isMulti && isSelected ? <Check size={14} /> : index + 1}
                      </span>
                    )}

                    <span className="flex-1 min-w-0">
                      <span className="block truncate text-[15px] font-medium text-foreground">
                        {option.label}
                      </span>
                      {option.description ? (
                        <span className="block text-[12px] text-muted-foreground mt-0.5 truncate">
                          {option.description}
                        </span>
                      ) : null}
                    </span>

                    {isSingle && isSelected ? (
                      <CornerDownLeft size={14} className="text-muted-foreground" />
                    ) : null}
                  </button>
                </div>
              )
            })}
          </div>
        </div>

        <div className="border-t border-border/60 bg-background/35 px-3 py-2.5">
          <div className="flex items-center gap-2">
            <PencilLine size={16} className="text-muted-foreground" />
            <input
              ref={freeformInputRef}
              value={freeformValue}
              onChange={(event) => setFreeformValue(event.target.value)}
              placeholder="Something else"
              disabled={isSubmitting}
              className={cn(
                'flex-1 bg-transparent text-[14px] text-foreground placeholder:text-muted-foreground',
                'outline-none'
              )}
            />
            {decision.skippable ? (
              <button
                type="button"
                onClick={() => void handleSkip()}
                disabled={isSubmitting}
                className={cn(
                  'rounded-lg border border-border px-4 py-1.5 text-[12px] font-medium text-foreground',
                  'bg-background/70 hover:bg-secondary transition-colors',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                Skip
              </button>
            ) : null}
          </div>
        </div>

        <div className="px-4 py-2.5 text-center text-[11px] text-muted-foreground/85">
          {isSubmitting ? (
            <span className="inline-flex items-center gap-1.5">
              <Loader2 size={12} className="animate-spin" />
              Submitting your choice...
            </span>
          ) : (
            KEYBOARD_HINT_TEXT
          )}
        </div>

        {error ? (
          <div className="px-4 pb-3 text-center text-[12px] text-destructive">{error}</div>
        ) : null}
      </div>
    </div>
  )
})
