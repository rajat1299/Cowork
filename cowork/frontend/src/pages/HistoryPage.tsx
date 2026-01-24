import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Clock,
  Search,
  Loader2,
  MessageSquare,
  Trash2,
  MoreVertical,
  AlertCircle,
  CheckCircle2,
  Circle,
  X,
  RefreshCw,
  Filter,
} from 'lucide-react'
import { cn } from '../lib/utils'
import { history } from '../api/coreApi'
import type { HistoryTask } from '../api/coreApi'
import { useChatStore } from '../stores/chatStore'

type StatusFilter = 'all' | 'ongoing' | 'completed'

/**
 * History page - view and manage past conversations
 * Fetches from GET /chat/histories
 */
export default function HistoryPage() {
  const navigate = useNavigate()
  const { setActiveTask } = useChatStore()

  // State
  const [histories, setHistories] = useState<HistoryTask[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [menuOpenId, setMenuOpenId] = useState<number | null>(null)

  // Fetch histories on mount
  useEffect(() => {
    fetchHistories()
  }, [])

  const fetchHistories = async () => {
    try {
      setIsLoading(true)
      setError(null)
      const data = await history.list(100, 0)
      setHistories(Array.isArray(data) ? data : [])
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load history'
      setError(message)
      setHistories([])
    } finally {
      setIsLoading(false)
    }
  }

  // Filter and search histories
  const filteredHistories = useMemo(() => {
    return histories.filter((item) => {
      // Status filter
      if (statusFilter === 'ongoing' && item.status !== 1) return false
      if (statusFilter === 'completed' && item.status !== 2) return false

      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        const matchesQuestion = item.question?.toLowerCase().includes(query)
        const matchesProject = item.project_name?.toLowerCase().includes(query)
        const matchesSummary = item.summary?.toLowerCase().includes(query)
        return matchesQuestion || matchesProject || matchesSummary
      }

      return true
    })
  }, [histories, searchQuery, statusFilter])

  // Group by date
  const groupedHistories = useMemo(() => {
    const groups: Record<string, HistoryTask[]> = {}

    filteredHistories.forEach((item) => {
      const date = new Date(item.created_at || Date.now())
      const key = getDateGroupKey(date)
      if (!groups[key]) groups[key] = []
      groups[key].push(item)
    })

    return Object.entries(groups).sort(([a], [b]) => {
      // Sort groups by recency (Today first)
      const order = ['Today', 'Yesterday', 'This Week', 'This Month', 'Older']
      return order.indexOf(a) - order.indexOf(b)
    })
  }, [filteredHistories])

  const handleHistoryClick = (item: HistoryTask) => {
    setActiveTask(item.task_id)
    navigate('/')
  }

  const handleDelete = async (id: number) => {
    try {
      setDeletingId(id)
      await history.delete(id)
      setHistories((prev) => prev.filter((h) => h.id !== id))
    } catch (err) {
      console.error('Failed to delete history:', err)
    } finally {
      setDeletingId(null)
      setMenuOpenId(null)
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 px-6 py-4 border-b border-dark-border">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-medium text-ink">History</h1>
            <p className="text-[13px] text-ink-subtle mt-0.5">
              {filteredHistories.length} conversation{filteredHistories.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button
            onClick={fetchHistories}
            disabled={isLoading}
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-xl',
              'bg-dark-surface border border-dark-border',
              'text-ink-muted text-[13px]',
              'hover:text-ink hover:border-ink-faint transition-colors',
              'disabled:opacity-50'
            )}
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {/* Search and filters */}
        <div className="flex items-center gap-3">
          {/* Search input */}
          <div className="flex-1 relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search conversations..."
              className={cn(
                'w-full pl-10 pr-4 py-2.5 rounded-xl',
                'bg-dark-surface border border-dark-border',
                'text-ink text-[14px] placeholder:text-ink-subtle',
                'focus:outline-none focus:border-burnt/50'
              )}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Status filter */}
          <div className="flex items-center gap-1 p-1 bg-dark-surface border border-dark-border rounded-xl">
            <FilterButton
              active={statusFilter === 'all'}
              onClick={() => setStatusFilter('all')}
            >
              All
            </FilterButton>
            <FilterButton
              active={statusFilter === 'ongoing'}
              onClick={() => setStatusFilter('ongoing')}
            >
              <Circle size={10} className="text-burnt" />
              Ongoing
            </FilterButton>
            <FilterButton
              active={statusFilter === 'completed'}
              onClick={() => setStatusFilter('completed')}
            >
              <CheckCircle2 size={10} className="text-green-500" />
              Completed
            </FilterButton>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto px-6 py-4">
        {/* Loading state */}
        {isLoading && histories.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16">
            <Loader2 size={32} className="animate-spin text-burnt mb-4" />
            <p className="text-ink-subtle text-[14px]">Loading history...</p>
          </div>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
              <AlertCircle size={24} className="text-red-400" />
            </div>
            <h2 className="text-lg font-medium text-ink mb-2">Failed to load history</h2>
            <p className="text-ink-subtle text-[14px] mb-4">{error}</p>
            <button
              onClick={fetchHistories}
              className={cn(
                'px-4 py-2 rounded-xl',
                'bg-burnt text-white text-[14px] font-medium',
                'hover:bg-burnt/90 transition-colors'
              )}
            >
              Try Again
            </button>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && histories.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-12 h-12 rounded-full bg-dark-surface flex items-center justify-center mb-4">
              <Clock size={24} className="text-ink-muted" />
            </div>
            <h2 className="text-lg font-medium text-ink mb-2">No history yet</h2>
            <p className="text-ink-subtle text-[14px]">
              Your conversation history will appear here.
            </p>
          </div>
        )}

        {/* No results from search */}
        {!isLoading && !error && histories.length > 0 && filteredHistories.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-12 h-12 rounded-full bg-dark-surface flex items-center justify-center mb-4">
              <Filter size={24} className="text-ink-muted" />
            </div>
            <h2 className="text-lg font-medium text-ink mb-2">No matches found</h2>
            <p className="text-ink-subtle text-[14px] mb-4">
              Try adjusting your search or filters.
            </p>
            <button
              onClick={() => {
                setSearchQuery('')
                setStatusFilter('all')
              }}
              className="text-burnt text-[14px] hover:underline"
            >
              Clear filters
            </button>
          </div>
        )}

        {/* History list grouped by date */}
        {!isLoading && !error && filteredHistories.length > 0 && (
          <div className="space-y-6">
            {groupedHistories.map(([groupKey, items]) => (
              <div key={groupKey}>
                <h3 className="text-[12px] font-medium text-ink-subtle uppercase tracking-wide mb-3">
                  {groupKey}
                </h3>
                <div className="space-y-2">
                  {items.map((item) => (
                    <HistoryCard
                      key={item.id}
                      item={item}
                      isDeleting={deletingId === Number(item.id)}
                      menuOpen={menuOpenId === Number(item.id)}
                      onMenuToggle={() => setMenuOpenId(menuOpenId === Number(item.id) ? null : Number(item.id))}
                      onClick={() => handleHistoryClick(item)}
                      onDelete={() => handleDelete(Number(item.id))}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

// ============ Components ============

interface FilterButtonProps {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}

function FilterButton({ active, onClick, children }: FilterButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px]',
        'transition-colors',
        active
          ? 'bg-dark-elevated text-ink'
          : 'text-ink-muted hover:text-ink'
      )}
    >
      {children}
    </button>
  )
}

interface HistoryCardProps {
  item: HistoryTask
  isDeleting: boolean
  menuOpen: boolean
  onMenuToggle: () => void
  onClick: () => void
  onDelete: () => void
}

function HistoryCard({
  item,
  isDeleting,
  menuOpen,
  onMenuToggle,
  onClick,
  onDelete,
}: HistoryCardProps) {
  const isOngoing = item.status === 1
  const date = new Date(item.created_at || Date.now())

  return (
    <div
      className={cn(
        'group flex items-start gap-3 p-4 rounded-xl',
        'bg-dark-surface border border-dark-border',
        'hover:border-ink-faint transition-colors cursor-pointer'
      )}
      onClick={onClick}
    >
      {/* Icon */}
      <div
        className={cn(
          'w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0',
          isOngoing ? 'bg-burnt/15' : 'bg-dark-elevated'
        )}
      >
        <MessageSquare
          size={16}
          className={isOngoing ? 'text-burnt' : 'text-ink-muted'}
        />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <h4 className="text-[14px] font-medium text-ink truncate">
            {item.project_name || truncateText(item.question, 60)}
          </h4>
          {isOngoing ? (
            <span className="flex items-center gap-1 text-[11px] text-burnt">
              <Circle size={8} fill="currentColor" />
              Ongoing
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[11px] text-green-500">
              <CheckCircle2 size={10} />
              Done
            </span>
          )}
        </div>
        <p className="text-[13px] text-ink-subtle truncate mb-2">
          {item.summary || truncateText(item.question, 100)}
        </p>
        <div className="flex items-center gap-3 text-[11px] text-ink-muted">
          <span>{formatTime(date)}</span>
          {item.model_type && (
            <>
              <span>·</span>
              <span>{item.model_type}</span>
            </>
          )}
          {item.tokens > 0 && (
            <>
              <span>·</span>
              <span>{item.tokens.toLocaleString()} tokens</span>
            </>
          )}
        </div>
      </div>

      {/* Menu */}
      <div className="relative">
        <button
          onClick={(e) => {
            e.stopPropagation()
            onMenuToggle()
          }}
          className={cn(
            'p-2 rounded-lg transition-colors',
            'opacity-0 group-hover:opacity-100',
            'hover:bg-dark-elevated'
          )}
        >
          {isDeleting ? (
            <Loader2 size={16} className="animate-spin text-ink-muted" />
          ) : (
            <MoreVertical size={16} className="text-ink-muted" />
          )}
        </button>

        {menuOpen && !isDeleting && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={(e) => {
                e.stopPropagation()
                onMenuToggle()
              }}
            />
            <div className="absolute right-0 top-full mt-1 z-20 w-36 py-1 bg-dark-surface border border-dark-border rounded-lg shadow-lg">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete()
                }}
                className="w-full px-3 py-2 text-left text-[13px] text-red-400 hover:bg-dark-elevated flex items-center gap-2"
              >
                <Trash2 size={14} />
                Delete
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ============ Utility Functions ============

function truncateText(text: string, maxLength: number): string {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength - 3) + '...'
}

function getDateGroupKey(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return 'This Week'
  if (diffDays < 30) return 'This Month'
  return 'Older'
}

function formatTime(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  })
}
