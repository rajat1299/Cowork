import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Share2,
  Clock,
  AlertCircle,
  Loader2,
  MessageSquare,
  Cpu,
  Globe,
  ArrowLeft,
} from 'lucide-react'
import { cn } from '../lib/utils'
import { share } from '../api/coreApi'
import type { ShareInfo } from '../api/coreApi'

/**
 * Public share page - view shared conversation
 * Fetches from GET /chat/share/info/{token}
 */
export default function SharePage() {
  const { token } = useParams<{ token: string }>()
  const [shareInfo, setShareInfo] = useState<ShareInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setError('No share token provided')
      setIsLoading(false)
      return
    }

    const fetchShareInfo = async () => {
      try {
        setIsLoading(true)
        setError(null)
        const info = await share.getInfo(token)
        setShareInfo(info)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load shared content'
        setError(message)
      } finally {
        setIsLoading(false)
      }
    }

    fetchShareInfo()
  }, [token])

  return (
    <div className="min-h-screen bg-dark-bg">
      {/* Header */}
      <header className="border-b border-dark-border px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-burnt/15 flex items-center justify-center">
              <Share2 size={16} className="text-burnt" />
            </div>
            <div>
              <h1 className="text-[15px] font-medium text-ink">Shared Conversation</h1>
              <p className="text-[12px] text-ink-subtle">View only</p>
            </div>
          </div>
          <Link
            to="/"
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 rounded-lg',
              'text-ink-muted text-[13px]',
              'hover:text-ink hover:bg-dark-surface transition-colors'
            )}
          >
            <ArrowLeft size={14} />
            Go to App
          </Link>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-3xl mx-auto px-6 py-8">
        {/* Loading state */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Loader2 size={32} className="animate-spin text-burnt mb-4" />
            <p className="text-ink-subtle text-[14px]">Loading shared content...</p>
          </div>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
              <AlertCircle size={24} className="text-red-400" />
            </div>
            <h2 className="text-lg font-medium text-ink mb-2">Unable to load</h2>
            <p className="text-ink-subtle text-[14px] mb-4 max-w-sm">
              {error}
            </p>
            <p className="text-ink-muted text-[12px]">
              This link may have expired or the content may no longer be available.
            </p>
          </div>
        )}

        {/* Share info display */}
        {shareInfo && !isLoading && (
          <div className="space-y-6">
            {/* Project/Title card */}
            <div className="p-6 rounded-2xl bg-dark-surface border border-dark-border">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-burnt/15 flex items-center justify-center flex-shrink-0">
                  <MessageSquare size={20} className="text-burnt" />
                </div>
                <div className="flex-1 min-w-0">
                  <h2 className="text-[17px] font-medium text-ink mb-1">
                    {shareInfo.project_name || 'Shared Conversation'}
                  </h2>
                  {shareInfo.summary && (
                    <p className="text-[14px] text-ink-subtle line-clamp-3">
                      {shareInfo.summary}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Question/Prompt */}
            <div className="p-5 rounded-xl bg-dark-elevated border border-dark-border">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-6 h-6 rounded-full bg-burnt/15 flex items-center justify-center">
                  <span className="text-[11px] font-medium text-burnt">U</span>
                </div>
                <span className="text-[12px] text-ink-subtle">User prompt</span>
              </div>
              <p className="text-[15px] text-ink leading-relaxed whitespace-pre-wrap">
                {shareInfo.question}
              </p>
            </div>

            {/* Metadata */}
            <div className="grid grid-cols-2 gap-4">
              {/* Model info */}
              <div className="p-4 rounded-xl bg-dark-surface border border-dark-border">
                <div className="flex items-center gap-2 mb-2">
                  <Cpu size={14} className="text-ink-subtle" />
                  <span className="text-[12px] text-ink-subtle">Model</span>
                </div>
                <p className="text-[14px] text-ink font-medium">
                  {shareInfo.model_type || 'Unknown'}
                </p>
                {shareInfo.model_platform && (
                  <p className="text-[12px] text-ink-muted mt-0.5">
                    {shareInfo.model_platform}
                  </p>
                )}
              </div>

              {/* Language */}
              <div className="p-4 rounded-xl bg-dark-surface border border-dark-border">
                <div className="flex items-center gap-2 mb-2">
                  <Globe size={14} className="text-ink-subtle" />
                  <span className="text-[12px] text-ink-subtle">Language</span>
                </div>
                <p className="text-[14px] text-ink font-medium">
                  {getLanguageLabel(shareInfo.language)}
                </p>
              </div>
            </div>

            {/* Footer note */}
            <div className="flex items-center justify-center gap-2 py-4 text-ink-muted text-[12px]">
              <Clock size={12} />
              <span>Share links expire after 24 hours</span>
            </div>
          </div>
        )}
      </main>

      {/* Branding footer */}
      <footer className="border-t border-dark-border py-4 mt-auto">
        <div className="max-w-3xl mx-auto px-6 flex items-center justify-center gap-2">
          <span className="text-[12px] text-ink-subtle">Powered by</span>
          <span className="text-[12px] font-medium text-ink">Cowork</span>
        </div>
      </footer>
    </div>
  )
}

/**
 * Get human-readable language label
 */
function getLanguageLabel(code: string): string {
  const languages: Record<string, string> = {
    en: 'English',
    zh: 'Chinese',
    es: 'Spanish',
    fr: 'French',
    de: 'German',
    ja: 'Japanese',
    ko: 'Korean',
    pt: 'Portuguese',
    ru: 'Russian',
    it: 'Italian',
  }
  return languages[code] || code.toUpperCase()
}
