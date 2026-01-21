import { useParams } from 'react-router-dom'
import { Share2, Clock } from 'lucide-react'

/**
 * Public share page - view shared conversation
 * TODO: Implement with GET /chat/share/info/{token}
 */
export default function SharePage() {
  const { token } = useParams<{ token: string }>()

  // TODO: Fetch share info using token
  // const { data, isLoading, error } = useShareInfo(token)

  return (
    <div className="min-h-screen bg-dark-bg">
      {/* Header */}
      <header className="border-b border-dark-border px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-burnt/15 flex items-center justify-center">
            <Share2 size={16} className="text-burnt" />
          </div>
          <div>
            <h1 className="text-[15px] font-medium text-ink">Shared Conversation</h1>
            <p className="text-[12px] text-ink-subtle">View only</p>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-12 h-12 rounded-full bg-dark-surface flex items-center justify-center mb-4">
            <Clock size={24} className="text-ink-muted" />
          </div>
          <h2 className="text-lg font-medium text-ink mb-2">Loading shared content...</h2>
          <p className="text-ink-subtle text-[14px] mb-4">
            Token: <code className="text-ink-muted">{token}</code>
          </p>
          <p className="text-ink-subtle text-[13px]">
            This feature will display the shared conversation history.
          </p>
        </div>
      </main>
    </div>
  )
}
