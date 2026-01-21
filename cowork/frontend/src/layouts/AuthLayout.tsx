import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores'

interface AuthLayoutProps {
  children: React.ReactNode
}

/**
 * Layout for auth pages (login, register)
 * Redirects to home if already authenticated
 */
export function AuthLayout({ children }: AuthLayoutProps) {
  const { isAuthenticated, isLoading } = useAuthStore()

  // Show loading while checking auth
  if (isLoading) {
    return (
      <div className="h-screen bg-dark-bg flex items-center justify-center">
        <div className="text-ink-subtle text-[14px]">Loading...</div>
      </div>
    )
  }

  // Redirect to home if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
