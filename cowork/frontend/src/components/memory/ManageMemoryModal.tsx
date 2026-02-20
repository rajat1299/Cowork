import { memo } from 'react'
import { X } from 'lucide-react'
import { cn } from '../../lib/utils'
import { MEMORY_CATEGORIES } from '../../hooks/useMemory'
import type { MemoryNote, MemoryCategory } from '../../api/coreApi'

interface ManageMemoryModalProps {
  open: boolean
  onClose: () => void
  notes: MemoryNote[]
  notesByCategory: Record<MemoryCategory, MemoryNote[]>
  onRefresh: () => void
}

/**
 * Modal to view and manage AI memory
 * Shows categorized memory notes the AI has learned about the user
 */
export function ManageMemoryModal({
  open,
  onClose,
  notesByCategory,
}: ManageMemoryModalProps) {
  if (!open) return null

  // Get categories that have content
  const categoriesWithContent = MEMORY_CATEGORIES.filter(
    (cat) => notesByCategory[cat.id]?.length > 0
  )

  // Check if any memory exists
  const hasMemory = categoriesWithContent.length > 0

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className={cn(
          'relative w-full max-w-2xl max-h-[80vh] mx-4',
          'bg-card border border-border rounded-2xl',
          'shadow-2xl shadow-black/50',
          'animate-scale-in'
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-xl font-medium text-foreground">Manage memory</h2>
          <button
            onClick={onClose}
            className={cn(
              'w-8 h-8 flex items-center justify-center rounded-lg',
              'text-muted-foreground hover:text-foreground',
              'hover:bg-secondary transition-colors'
            )}
          >
            <X size={18} />
          </button>
        </div>

        {/* Description */}
        <div className="px-6 py-4 border-b border-border">
          <p className="text-[14px] text-muted-foreground">
            Here's what Cowork remembers about you! This summary is regenerated each night and does
            not include projects, which have their own specific memory.
          </p>
        </div>

        {/* Memory Content */}
        <div className="px-6 py-4 overflow-y-auto max-h-[60vh]">
          {!hasMemory ? (
            <div className="text-center py-12">
              <p className="text-[14px] text-muted-foreground">
                No memory saved yet. As you chat with Cowork, relevant context will be remembered
                here.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {categoriesWithContent.map((category) => {
                const categoryNotes = notesByCategory[category.id] || []
                // Combine all notes in this category into one block
                const combinedContent = categoryNotes
                  .map((note) => note.content)
                  .join('\n\n')

                return (
                  <MemorySection
                    key={category.id}
                    title={category.label}
                    content={combinedContent}
                  />
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border flex justify-end">
          <button
            onClick={onClose}
            className={cn(
              'px-4 py-2 rounded-lg',
              'bg-secondary border border-border',
              'text-[14px] text-foreground',
              'hover:bg-accent transition-colors'
            )}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

interface MemorySectionProps {
  title: string
  content: string
}

const MemorySection = memo(function MemorySection({ title, content }: MemorySectionProps) {
  return (
    <div>
      <h3 className="text-[15px] font-medium text-foreground mb-2">{title}</h3>
      <p className="text-[14px] text-muted-foreground leading-relaxed whitespace-pre-wrap">
        {content}
      </p>
    </div>
  )
})

export default ManageMemoryModal
