import { useState, useEffect, useCallback } from 'react'
import {
  memory,
  type MemoryContextStats,
  type MemoryNote,
  type MemoryCategory,
  type CreateMemoryNoteRequest,
  type UpdateMemoryNoteRequest,
} from '../api/coreApi'

// Default project ID for global memory
const DEFAULT_PROJECT_ID = 'GLOBAL_USER_CONTEXT'

// Memory categories in display order
export const MEMORY_CATEGORIES: { id: MemoryCategory; label: string }[] = [
  { id: 'work_context', label: 'Work context' },
  { id: 'personal_context', label: 'Personal context' },
  { id: 'top_of_mind', label: 'Top of mind' },
  { id: 'brief_history', label: 'Brief history' },
  { id: 'earlier_context', label: 'Earlier context' },
  { id: 'long_term_background', label: 'Long-term background' },
]

export interface UseMemoryOptions {
  projectId?: string
  autoFetch?: boolean
}

export interface UseMemoryReturn {
  // State
  stats: MemoryContextStats | null
  notes: MemoryNote[]
  notesByCategory: Record<MemoryCategory, MemoryNote[]>
  isLoading: boolean
  error: string | null

  // Actions
  fetchStats: () => Promise<void>
  fetchNotes: (category?: MemoryCategory) => Promise<void>
  createNote: (data: Omit<CreateMemoryNoteRequest, 'project_id'>) => Promise<MemoryNote | null>
  updateNote: (noteId: number, data: UpdateMemoryNoteRequest) => Promise<MemoryNote | null>
  deleteNote: (noteId: number) => Promise<boolean>
  refresh: () => Promise<void>
}

/**
 * Hook for managing memory notes and context stats
 */
export function useMemory(options: UseMemoryOptions = {}): UseMemoryReturn {
  const { projectId = DEFAULT_PROJECT_ID, autoFetch = true } = options

  const [stats, setStats] = useState<MemoryContextStats | null>(null)
  const [notes, setNotes] = useState<MemoryNote[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Group notes by category
  const notesByCategory = notes.reduce<Record<MemoryCategory, MemoryNote[]>>(
    (acc, note) => {
      if (!acc[note.category]) {
        acc[note.category] = []
      }
      acc[note.category].push(note)
      return acc
    },
    {} as Record<MemoryCategory, MemoryNote[]>
  )

  const fetchStats = useCallback(async () => {
    try {
      const data = await memory.getContextStats(projectId)
      setStats(data)
    } catch (err) {
      console.error('Failed to fetch memory stats:', err)
      setError('Failed to load memory stats')
    }
  }, [projectId])

  const fetchNotes = useCallback(
    async (category?: MemoryCategory) => {
      try {
        const data = await memory.listNotes(projectId, category)
        if (category) {
          // Merge with existing notes for other categories
          setNotes((prev) => {
            const filtered = prev.filter((n) => n.category !== category)
            return [...filtered, ...data]
          })
        } else {
          setNotes(data)
        }
      } catch (err) {
        console.error('Failed to fetch memory notes:', err)
        setError('Failed to load memory notes')
      }
    },
    [projectId]
  )

  const refresh = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      await Promise.all([fetchStats(), fetchNotes()])
    } finally {
      setIsLoading(false)
    }
  }, [fetchStats, fetchNotes])

  const createNote = useCallback(
    async (data: Omit<CreateMemoryNoteRequest, 'project_id'>): Promise<MemoryNote | null> => {
      try {
        const note = await memory.createNote({ ...data, project_id: projectId })
        setNotes((prev) => [...prev, note])
        return note
      } catch (err) {
        console.error('Failed to create memory note:', err)
        setError('Failed to create memory note')
        return null
      }
    },
    [projectId]
  )

  const updateNote = useCallback(
    async (noteId: number, data: UpdateMemoryNoteRequest): Promise<MemoryNote | null> => {
      try {
        const updated = await memory.updateNote(noteId, data)
        setNotes((prev) => prev.map((n) => (n.id === noteId ? updated : n)))
        return updated
      } catch (err) {
        console.error('Failed to update memory note:', err)
        setError('Failed to update memory note')
        return null
      }
    },
    []
  )

  const deleteNote = useCallback(async (noteId: number): Promise<boolean> => {
    try {
      await memory.deleteNote(noteId)
      setNotes((prev) => prev.filter((n) => n.id !== noteId))
      return true
    } catch (err) {
      console.error('Failed to delete memory note:', err)
      setError('Failed to delete memory note')
      return false
    }
  }, [])

  // Auto-fetch on mount
  useEffect(() => {
    if (autoFetch) {
      refresh()
    }
  }, [autoFetch, refresh])

  return {
    stats,
    notes,
    notesByCategory,
    isLoading,
    error,
    fetchStats,
    fetchNotes,
    createNote,
    updateNote,
    deleteNote,
    refresh,
  }
}

/**
 * Format relative time for memory last updated
 */
export function formatMemoryLastUpdated(isoString: string | null): string {
  if (!isoString) return 'Never updated'

  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffHours / 24)

  if (diffHours < 1) {
    const diffMinutes = Math.floor(diffMs / (1000 * 60))
    if (diffMinutes < 1) return 'Just now'
    return `Updated ${diffMinutes} minute${diffMinutes === 1 ? '' : 's'} ago`
  }

  if (diffHours < 24) {
    return `Updated ${diffHours} hour${diffHours === 1 ? '' : 's'} ago`
  }

  if (diffDays < 7) {
    return `Updated ${diffDays} day${diffDays === 1 ? '' : 's'} ago`
  }

  return `Updated on ${date.toLocaleDateString()}`
}
