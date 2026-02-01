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
  // Use individual selectors to avoid re-renders on unrelated state changes
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const isLoading = useAuthStore((s) => s.isLoading)

  // Show loading while checking auth
  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-muted-foreground text-[14px]">Loading...</div>
      </div>
    )
  }

  // Redirect to home if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
