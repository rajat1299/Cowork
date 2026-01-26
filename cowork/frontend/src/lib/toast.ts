import { toast } from 'sonner'
import { ApiError } from '../api/client'

/**
 * Show a success toast
 */
export function showSuccess(message: string, description?: string) {
  toast.success(message, { description })
}

/**
 * Show an error toast
 */
export function showError(message: string, description?: string) {
  toast.error(message, { description })
}

/**
 * Show an info toast
 */
export function showInfo(message: string, description?: string) {
  toast.info(message, { description })
}

/**
 * Show a loading toast that can be updated
 */
export function showLoading(message: string) {
  return toast.loading(message)
}

/**
 * Dismiss a specific toast by ID
 */
export function dismissToast(id: string | number) {
  toast.dismiss(id)
}

/**
 * Extract a user-friendly error message from an error
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    // Try to extract message from API error data
    const data = error.data as Record<string, unknown> | null
    if (data?.detail && typeof data.detail === 'string') {
      return data.detail
    }
    if (data?.message && typeof data.message === 'string') {
      return data.message
    }
    // Fall back to status text
    return error.statusText || 'Request failed'
  }

  if (error instanceof Error) {
    return error.message
  }

  if (typeof error === 'string') {
    return error
  }

  return 'An unexpected error occurred'
}

/**
 * Show an error toast from an error object
 */
export function showErrorFromError(error: unknown, fallbackMessage = 'An error occurred') {
  const message = getErrorMessage(error)
  showError(fallbackMessage, message !== fallbackMessage ? message : undefined)
}

/**
 * Wrap an async function with automatic error toast handling
 */
export async function withErrorToast<T>(
  fn: () => Promise<T>,
  errorMessage = 'Operation failed'
): Promise<T | null> {
  try {
    return await fn()
  } catch (error) {
    showErrorFromError(error, errorMessage)
    return null
  }
}

/**
 * Wrap an async function with loading and success/error toasts
 */
export async function withToast<T>(
  fn: () => Promise<T>,
  options: {
    loading?: string
    success?: string
    error?: string
  } = {}
): Promise<T | null> {
  const { loading = 'Loading...', success = 'Done!', error = 'Failed' } = options

  const toastId = showLoading(loading)

  try {
    const result = await fn()
    toast.success(success, { id: toastId })
    return result
  } catch (err) {
    const message = getErrorMessage(err)
    toast.error(error, { id: toastId, description: message !== error ? message : undefined })
    return null
  }
}
