import { Skeleton } from './skeleton'
import { cn } from '@/lib/utils'

/**
 * Skeleton for a card/list item with icon, title, and description
 */
export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-start gap-3 p-4 rounded-xl bg-secondary border border-border', className)}>
      <Skeleton className="w-10 h-10 rounded-lg flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-3 w-2/3" />
      </div>
    </div>
  )
}

/**
 * Skeleton for a settings row with label and value
 */
export function SettingsRowSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center justify-between py-3', className)}>
      <div className="space-y-1">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-3 w-40" />
      </div>
      <Skeleton className="h-8 w-20 rounded-lg" />
    </div>
  )
}

/**
 * Skeleton for a history/conversation item
 */
export function HistoryItemSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-start gap-3 p-4 rounded-xl bg-secondary border border-border', className)}>
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <div className="flex items-center gap-2">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-3 w-24" />
        </div>
      </div>
      <Skeleton className="h-6 w-6 rounded" />
    </div>
  )
}

/**
 * Skeleton for a sidebar session item
 */
export function SessionItemSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-2 px-3 py-2 rounded-lg', className)}>
      <Skeleton className="w-4 h-4 rounded flex-shrink-0" />
      <Skeleton className="h-3 flex-1" />
    </div>
  )
}

/**
 * Skeleton for a provider card
 */
export function ProviderCardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('p-4 rounded-xl bg-secondary border border-border', className)}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <Skeleton className="w-10 h-10 rounded-lg" />
          <div className="space-y-1">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-16" />
          </div>
        </div>
        <Skeleton className="h-5 w-12 rounded-full" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-2/3" />
      </div>
    </div>
  )
}

/**
 * Skeleton for MCP server item
 */
export function MCPItemSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('p-4 rounded-xl bg-secondary border border-border', className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skeleton className="w-8 h-8 rounded-lg" />
          <div className="space-y-1">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-48" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-10 rounded-full" />
          <Skeleton className="h-8 w-8 rounded-lg" />
        </div>
      </div>
    </div>
  )
}

/**
 * Full page loading skeleton
 */
export function PageSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('p-6 space-y-6', className)}>
      <div className="space-y-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="space-y-4">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    </div>
  )
}

/**
 * Empty state component
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-12 text-center', className)}>
      {icon && <div className="mb-4 text-muted-foreground">{icon}</div>}
      <h3 className="text-[16px] font-medium text-foreground mb-1">{title}</h3>
      {description && <p className="text-[13px] text-muted-foreground mb-4 max-w-sm">{description}</p>}
      {action}
    </div>
  )
}

/**
 * Error state component
 */
export function ErrorState({
  title = 'Something went wrong',
  description,
  retry,
  className,
}: {
  title?: string
  description?: string
  retry?: () => void
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-12 text-center', className)}>
      <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-red-500">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h3 className="text-[16px] font-medium text-foreground mb-1">{title}</h3>
      {description && <p className="text-[13px] text-muted-foreground mb-4 max-w-sm">{description}</p>}
      {retry && (
        <button
          onClick={retry}
          className="px-4 py-2 text-[13px] font-medium text-foreground bg-secondary border border-border rounded-lg hover:bg-accent transition-colors"
        >
          Try again
        </button>
      )}
    </div>
  )
}
