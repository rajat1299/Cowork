import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronDown, Copy, Mail, Send } from 'lucide-react'
import { isDesktop } from '../../api/client'
import { showError, showSuccess } from '../../lib/toast'
import { cn } from '../../lib/utils'
import type { ComposeData, ComposeVariant } from '../../types/chat'

interface ComposeWidgetProps {
  composeData: ComposeData
}

type EmailTarget = 'gmail' | 'outlook' | 'mail_app'

const EMAIL_TARGET_LABELS: Record<EmailTarget, string> = {
  gmail: 'Send via Gmail',
  outlook: 'Send via Outlook',
  mail_app: 'Open Mail App',
}

const NON_EMAIL_ACTION_LABELS: Record<Exclude<ComposeData['platform'], 'email'>, string> = {
  slack: 'Copy for Slack',
  linkedin: 'Copy for LinkedIn',
  text: 'Copy as Text',
  generic: 'Copy Draft',
}

function getNonEmailActionLabel(platform: ComposeData['platform']): string {
  if (platform === 'email') return 'Copy Draft'
  return NON_EMAIL_ACTION_LABELS[platform]
}

function variantLetter(index: number): string {
  return String.fromCharCode(65 + index)
}

function buildEmailUrl(params: {
  target: EmailTarget
  subject?: string
  body: string
  recipient?: string
}): string {
  const { target, subject, body, recipient } = params
  const encodedBody = encodeURIComponent(body)
  const encodedSubject = encodeURIComponent(subject || '')
  const encodedRecipient = encodeURIComponent(recipient || '')

  if (target === 'gmail') {
    const toParam = encodedRecipient ? `&to=${encodedRecipient}` : ''
    return `https://mail.google.com/mail/?view=cm&fs=1&su=${encodedSubject}&body=${encodedBody}${toParam}`
  }

  if (target === 'outlook') {
    const toParam = encodedRecipient ? `&to=${encodedRecipient}` : ''
    return `https://outlook.office.com/mail/deeplink/compose?subject=${encodedSubject}&body=${encodedBody}${toParam}`
  }

  const queryParts = [`subject=${encodedSubject}`, `body=${encodedBody}`]
  return `mailto:${encodedRecipient}?${queryParts.join('&')}`
}

async function openExternal(url: string): Promise<void> {
  const desktop = (
    window as Window & {
      coworkDesktop?: { openExternal?: (target: string) => Promise<unknown> }
    }
  ).coworkDesktop

  if (isDesktop && desktop?.openExternal) {
    await desktop.openExternal(url)
    return
  }

  if (url.startsWith('mailto:')) {
    window.location.href = url
    return
  }

  window.open(url, '_blank', 'noopener,noreferrer')
}

async function copyText(value: string): Promise<void> {
  await navigator.clipboard.writeText(value)
}

function getInitialVariant(variants: ComposeVariant[]): ComposeVariant | null {
  return variants[0] || null
}

export const ComposeWidget = memo(function ComposeWidget({ composeData }: ComposeWidgetProps) {
  const [selectedVariantId, setSelectedVariantId] = useState<string>(
    () => getInitialVariant(composeData.variants)?.id || ''
  )
  const [emailTarget, setEmailTarget] = useState<EmailTarget>('gmail')
  const [emailMenuOpen, setEmailMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const selectedVariant = useMemo(() => {
    if (composeData.variants.length === 0) return null
    return (
      composeData.variants.find((variant) => variant.id === selectedVariantId) ||
      composeData.variants[0]
    )
  }, [composeData.variants, selectedVariantId])

  const recipient = composeData.metadata?.recipient
  const isEmail = composeData.platform === 'email'

  useEffect(() => {
    if (!emailMenuOpen) return

    const handleClickOutside = (event: MouseEvent) => {
      if (!menuRef.current) return
      if (!menuRef.current.contains(event.target as Node)) {
        setEmailMenuOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [emailMenuOpen])

  const handleCopyBody = useCallback(async () => {
    if (!selectedVariant) return
    try {
      await copyText(selectedVariant.body)
      showSuccess('Copied!', 'Draft body copied to clipboard.')
    } catch (error) {
      console.error('Failed to copy compose draft:', error)
      showError('Copy failed', 'Unable to copy draft text.')
    }
  }, [selectedVariant])

  const handleEmailAction = useCallback(
    async (target: EmailTarget) => {
      if (!selectedVariant) return
      const url = buildEmailUrl({
        target,
        subject: selectedVariant.subject,
        body: selectedVariant.body,
        recipient,
      })
      try {
        await openExternal(url)
      } catch (error) {
        console.error('Failed to open email compose link:', error)
        showError('Unable to open mail client')
      }
    },
    [recipient, selectedVariant]
  )

  const handlePlatformAction = useCallback(async () => {
    if (!selectedVariant) return

    if (isEmail) {
      await handleEmailAction(emailTarget)
      return
    }

    try {
      await copyText(selectedVariant.body)
      showSuccess('Copied!', `${getNonEmailActionLabel(composeData.platform)} ready.`)
    } catch (error) {
      console.error('Failed to copy platform draft:', error)
      showError('Copy failed', 'Unable to copy draft text.')
    }
  }, [composeData.platform, emailTarget, handleEmailAction, isEmail, selectedVariant])

  if (!selectedVariant) return null

  return (
    <div className="w-full rounded-2xl border border-border/70 bg-card/85 shadow-sm overflow-hidden animate-fade-in">
      <div className="flex items-center gap-2 border-b border-border/55 px-3 py-2">
        <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
          {composeData.contractVersion ? `contract ${composeData.contractVersion}` : 'legacy contract'}
        </span>
        {composeData.variants.map((variant, index) => {
          const active = selectedVariant.id === variant.id
          return (
            <button
              key={variant.id}
              type="button"
              onClick={() => setSelectedVariantId(variant.id)}
              className={cn(
                'inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-[13px] transition-colors',
                active
                  ? 'bg-blue-500/15 text-blue-400'
                  : 'text-muted-foreground hover:text-foreground hover:bg-secondary/60'
              )}
            >
              <span
                className={cn(
                  'inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-semibold',
                  active ? 'bg-blue-500 text-white' : 'bg-muted text-muted-foreground'
                )}
              >
                {variantLetter(index)}
              </span>
              <span className="font-medium">{variant.label}</span>
            </button>
          )
        })}
      </div>

      {isEmail && selectedVariant.subject ? (
        <div className="border-b border-border/45 px-4 py-2 text-[13px] text-foreground">
          <span className="text-muted-foreground mr-2">Subject:</span>
          <span className="font-medium">{selectedVariant.subject}</span>
        </div>
      ) : null}

      {composeData.metadata && Object.keys(composeData.metadata).length > 0 ? (
        <div className="border-b border-border/45 px-4 py-2 text-[11px] text-muted-foreground">
          {Object.entries(composeData.metadata)
            .slice(0, 4)
            .map(([key, value]) => `${key}: ${value}`)
            .join(' · ')}
        </div>
      ) : null}

      <div className="px-4 py-4">
        <pre className="whitespace-pre-wrap break-words text-[14px] leading-7 text-foreground font-sans">
          {selectedVariant.body}
        </pre>
      </div>

      <div className="border-t border-border/50 px-3 py-2 flex items-center justify-end gap-1.5">
        <button
          type="button"
          onClick={() => void handleCopyBody()}
          className={cn(
            'inline-flex items-center justify-center rounded-lg border border-border px-2.5 py-1.5',
            'text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors'
          )}
          aria-label="Copy draft"
        >
          <Copy size={14} />
        </button>

        {isEmail ? (
          <div ref={menuRef} className="relative inline-flex items-center">
            <button
              type="button"
              onClick={() => void handlePlatformAction()}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-l-lg border border-r-0 border-border px-3 py-1.5 text-[13px] font-medium',
                'text-foreground hover:bg-secondary transition-colors'
              )}
            >
              {emailTarget === 'gmail' ? <Mail size={14} /> : <Send size={14} />}
              {EMAIL_TARGET_LABELS[emailTarget]}
            </button>
            <button
              type="button"
              onClick={() => setEmailMenuOpen((open) => !open)}
              className={cn(
                'inline-flex items-center justify-center rounded-r-lg border border-border px-2 py-1.5',
                'text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors'
              )}
              aria-label="Choose email provider"
            >
              <ChevronDown size={14} />
            </button>

            {emailMenuOpen ? (
              <div className="absolute right-0 top-full z-20 mt-1.5 w-44 rounded-lg border border-border bg-card shadow-lg">
                {(Object.keys(EMAIL_TARGET_LABELS) as EmailTarget[]).map((target) => (
                  <button
                    key={target}
                    type="button"
                    onClick={() => {
                      setEmailTarget(target)
                      setEmailMenuOpen(false)
                      void handleEmailAction(target)
                    }}
                    className={cn(
                      'w-full flex items-center justify-between px-3 py-2 text-[13px] text-left transition-colors',
                      'hover:bg-secondary first:rounded-t-lg last:rounded-b-lg',
                      emailTarget === target ? 'text-foreground' : 'text-muted-foreground'
                    )}
                  >
                    {EMAIL_TARGET_LABELS[target]}
                    {emailTarget === target ? <Check size={13} /> : null}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <button
            type="button"
            onClick={() => void handlePlatformAction()}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-[13px] font-medium',
              'text-foreground hover:bg-secondary transition-colors'
            )}
          >
            {getNonEmailActionLabel(composeData.platform)}
          </button>
        )}
      </div>
    </div>
  )
})
