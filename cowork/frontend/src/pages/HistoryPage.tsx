import { Clock } from 'lucide-react'

/**
 * History page - view past conversations
 * TODO: Implement with GET /chat/histories
 */
export default function HistoryPage() {
  return (
    <div className="h-full flex flex-col items-center justify-center px-6">
      <div className="w-full max-w-md text-center">
        <div className="w-12 h-12 rounded-full bg-dark-surface flex items-center justify-center mx-auto mb-4">
          <Clock size={24} className="text-ink-muted" />
        </div>
        <h1 className="text-xl font-medium text-ink mb-2">History</h1>
        <p className="text-ink-subtle text-[14px]">
          Your conversation history will appear here.
        </p>
      </div>
    </div>
  )
}
