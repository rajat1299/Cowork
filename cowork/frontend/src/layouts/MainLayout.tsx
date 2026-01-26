import { useState } from 'react'
import { Outlet, Navigate } from 'react-router-dom'
import { Sidebar, RightSidebar } from '../components/layout'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { useAuthStore } from '../stores'

/**
 * Main layout for authenticated pages
 * Includes sidebar navigation and right sidebar
 */
export function MainLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const { isAuthenticated, isLoading } = useAuthStore()

  // Show loading while checking auth
  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-muted-foreground text-[14px]">Loading...</div>
      </div>
    )
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="h-screen flex">
      {/* Left Sidebar - frosted glass effect */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-hidden">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>

      {/* Right Sidebar */}
      <RightSidebar />
    </div>
  )
}
