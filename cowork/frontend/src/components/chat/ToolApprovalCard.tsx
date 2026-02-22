import { memo, useState, useCallback, useEffect, useRef } from 'react'
import { Shield, Check, X, Loader2 } from 'lucide-react'
import { cn } from '../../lib/utils'
import { permission } from '../../api/orchestrator'
import { useChatStore } from '../../stores/chatStore'
import type { ToolApprovalData } from '../../types/chat'

interface ToolApprovalCardProps {
  approval: ToolApprovalData
}

const APPROVAL_TIMEOUT_SECONDS = 120

export const ToolApprovalCard = memo(function ToolApprovalCard({ approval }: ToolApprovalCardProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [remember, setRemember] = useState(true)
  const [secondsLeft, setSecondsLeft] = useState(APPROVAL_TIMEOUT_SECONDS)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const resolveApproval = useChatStore((s) => s.resolveApproval)

  // Countdown timer for pending approvals
  useEffect(() => {
    if (approval.status !== 'pending') return

    timerRef.current = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [approval.status])

  const handleDecision = useCallback(async (approved: boolean) => {
    if (isSubmitting || approval.status !== 'pending') return
    setIsSubmitting(true)

    try {
      await permission.submit(
        approval.projectId,
        approval.requestId,
        approved,
        approved && approval.tier === 'ask_once' ? remember : false,
      )
      resolveApproval(approval.requestId, approved ? 'approved' : 'denied')
    } catch (err) {
      console.error('Failed to submit permission decision:', err)
      setIsSubmitting(false)
    }
  }, [approval, isSubmitting, remember, resolveApproval])

  // Resolved state — compact single line
  if (approval.status === 'approved' || approval.status === 'denied') {
    const isApproved = approval.status === 'approved'
    return (
      <div
        className={cn(
          'flex items-center gap-2 px-3 py-2 rounded-lg text-[13px]',
          isApproved
            ? 'bg-emerald-500/5 text-emerald-400 border border-emerald-500/10'
            : 'bg-red-500/5 text-red-400 border border-red-500/10'
        )}
      >
        {isApproved ? <Check size={14} /> : <X size={14} />}
        <span className="text-muted-foreground">{approval.question}</span>
        <span className="font-medium ml-auto">
          {isApproved ? 'Allowed' : 'Denied'}
        </span>
      </div>
    )
  }

  // Pending state — full card with buttons
  return (
    <div className="rounded-lg border border-border bg-card/50 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border/50">
        <Shield size={16} className="text-amber-400 flex-shrink-0" />
        <span className="text-[13px] font-medium text-foreground">Permission Required</span>
        {secondsLeft > 0 && secondsLeft < 60 && (
          <span className="text-[11px] text-muted-foreground ml-auto">
            Auto-deciding in {secondsLeft}s
          </span>
        )}
      </div>

      {/* Body */}
      <div className="px-4 py-3">
        <p className="text-[13px] text-foreground">{approval.question}</p>
        {approval.detail && (
          <p className="text-[12px] text-muted-foreground mt-1">{approval.detail}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 px-4 py-3 border-t border-border/50 bg-muted/30">
        <button
          onClick={() => handleDecision(true)}
          disabled={isSubmitting}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[13px] font-medium',
            'bg-emerald-600 text-white hover:bg-emerald-500',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'transition-colors'
          )}
        >
          {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
          Allow
        </button>
        <button
          onClick={() => handleDecision(false)}
          disabled={isSubmitting}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[13px] font-medium',
            'bg-secondary text-muted-foreground hover:text-foreground hover:bg-secondary/80',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'transition-colors border border-border'
          )}
        >
          <X size={14} />
          Deny
        </button>

        {/* Remember checkbox — only for ask_once tier */}
        {approval.tier === 'ask_once' && (
          <label className="flex items-center gap-1.5 ml-auto cursor-pointer select-none">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="rounded border-border text-emerald-600 focus:ring-emerald-500/20 h-3.5 w-3.5"
            />
            <span className="text-[11px] text-muted-foreground">Remember for this session</span>
          </label>
        )}
      </div>
    </div>
  )
})
