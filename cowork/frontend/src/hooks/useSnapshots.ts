import { useState, useCallback } from 'react'
import { snapshots as snapshotsApi } from '../api/coreApi'
import type { Snapshot, CreateSnapshotRequest } from '../api/coreApi'

// ============ Hook State ============

interface UseSnapshotsState {
  snapshots: Snapshot[]
  isLoading: boolean
  error: string | null
}

interface UseSnapshotsReturn extends UseSnapshotsState {
  // Actions
  fetchSnapshots: (taskId: string) => Promise<void>
  createSnapshot: (data: CreateSnapshotRequest) => Promise<Snapshot | null>
  deleteSnapshot: (id: number) => Promise<boolean>
  getImageUrl: (id: number) => string
  clearSnapshots: () => void
  clearError: () => void
}

// ============ Hook Implementation ============

export function useSnapshots(): UseSnapshotsReturn {
  const [state, setState] = useState<UseSnapshotsState>({
    snapshots: [],
    isLoading: false,
    error: null,
  })

  const fetchSnapshots = useCallback(async (taskId: string) => {
    setState((s) => ({ ...s, isLoading: true, error: null }))
    try {
      const data = await snapshotsApi.list(taskId)
      setState((s) => ({
        ...s,
        snapshots: Array.isArray(data) ? data : [],
        isLoading: false,
      }))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch snapshots'
      setState((s) => ({ ...s, error: message, isLoading: false }))
    }
  }, [])

  const createSnapshot = useCallback(async (data: CreateSnapshotRequest): Promise<Snapshot | null> => {
    setState((s) => ({ ...s, isLoading: true, error: null }))
    try {
      const result = await snapshotsApi.create(data)
      setState((s) => ({
        ...s,
        snapshots: [...s.snapshots, result],
        isLoading: false,
      }))
      return result
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create snapshot'
      setState((s) => ({ ...s, error: message, isLoading: false }))
      return null
    }
  }, [])

  const deleteSnapshot = useCallback(async (id: number): Promise<boolean> => {
    setState((s) => ({ ...s, error: null }))
    try {
      await snapshotsApi.delete(id)
      setState((s) => ({
        ...s,
        snapshots: s.snapshots.filter((snap) => snap.id !== id),
      }))
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete snapshot'
      setState((s) => ({ ...s, error: message }))
      return false
    }
  }, [])

  const getImageUrl = useCallback((id: number): string => {
    return snapshotsApi.getImageUrl(id)
  }, [])

  const clearSnapshots = useCallback(() => {
    setState((s) => ({ ...s, snapshots: [] }))
  }, [])

  const clearError = useCallback(() => {
    setState((s) => ({ ...s, error: null }))
  }, [])

  return {
    ...state,
    fetchSnapshots,
    createSnapshot,
    deleteSnapshot,
    getImageUrl,
    clearSnapshots,
    clearError,
  }
}
