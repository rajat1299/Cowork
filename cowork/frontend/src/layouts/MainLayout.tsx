import { useEffect, useRef, useState } from 'react'
import { Outlet, Navigate, useLocation } from 'react-router-dom'
import { PanelRight } from 'lucide-react'
import { Sidebar, RightSidebar } from '../components/layout'
import { ArtifactViewerPane } from '../components/layout/ArtifactViewerPane'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { useAuthStore } from '../stores'
import { useViewerStore } from '../stores/viewerStore'
import { cn } from '../lib/utils'

/**
 * Main layout for authenticated pages
 * Includes sidebar navigation and right sidebar
 */
export function MainLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [rightSidebarCollapsed, setRightSidebarCollapsed] = useState(false)
  const [isResizing, setIsResizing] = useState(false)
  const mainContentRef = useRef<HTMLDivElement>(null)
  const location = useLocation()
  // Use individual selectors to avoid re-renders on unrelated state changes
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const isLoading = useAuthStore((s) => s.isLoading)
  const openedArtifact = useViewerStore((state) => state.artifact)
  const widthRatio = useViewerStore((state) => state.widthRatio)
  const setWidthRatio = useViewerStore((state) => state.setWidthRatio)
  const isArtifactOpen = Boolean(openedArtifact)

  // Hide right sidebar on non-chat routes (settings, history, etc.)
  const isChatRoute = location.pathname === '/'
  const showRightSidebar = isChatRoute && !isArtifactOpen && !rightSidebarCollapsed

  useEffect(() => {
    if (!isResizing) return undefined

    const handleMouseMove = (event: MouseEvent) => {
      const layoutNode = mainContentRef.current
      if (!layoutNode) return
      const bounds = layoutNode.getBoundingClientRect()
      if (bounds.width <= 0) return
      const rightWidth = bounds.right - event.clientX
      setWidthRatio(rightWidth / bounds.width)
    }

    const handleMouseUp = () => {
      setIsResizing(false)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isResizing, setWidthRatio])

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
      <main className="flex-1 min-w-0 content-overlay transition-colors duration-300">
        <div ref={mainContentRef} className="h-full flex min-w-0">
          <div
            className="min-w-0 h-full overflow-hidden"
            style={isArtifactOpen ? { width: `${(1 - widthRatio) * 100}%` } : { width: '100%' }}
          >
            <ErrorBoundary>
              <Outlet />
            </ErrorBoundary>
          </div>

          {isArtifactOpen ? (
            <>
              <button
                onMouseDown={() => setIsResizing(true)}
                className="w-1.5 h-full bg-border/80 hover:bg-foreground/30 transition-colors cursor-col-resize"
                aria-label="Resize preview pane"
              />
              <div className="h-full min-w-[360px]" style={{ width: `${widthRatio * 100}%` }}>
                <ArtifactViewerPane />
              </div>
            </>
          ) : null}
        </div>
      </main>

      {/* Right Sidebar */}
      {isChatRoute && !isArtifactOpen && (
        <div
          className={cn(
            'h-full overflow-hidden transition-all duration-300 ease-smooth',
            rightSidebarCollapsed ? 'w-0' : 'w-80'
          )}
        >
          <RightSidebar onCollapse={() => setRightSidebarCollapsed(true)} />
        </div>
      )}

      {/* Expand button when right sidebar is collapsed */}
      {isChatRoute && !isArtifactOpen && (
        <button
          onClick={() => setRightSidebarCollapsed(false)}
          aria-label="Expand sidebar"
          className={cn(
            'fixed right-4 top-4 z-10',
            'w-8 h-8 flex items-center justify-center',
            'text-muted-foreground hover:text-foreground',
            'rounded-lg',
            'transition-all duration-300 ease-smooth',
            rightSidebarCollapsed
              ? 'opacity-100 pointer-events-auto'
              : 'opacity-0 pointer-events-none'
          )}
        >
          <PanelRight size={18} strokeWidth={1.5} />
        </button>
      )}
    </div>
  )
}
