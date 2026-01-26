import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { MainLayout } from './layouts/MainLayout'
import { AuthLayout } from './layouts/AuthLayout'

// Lazy load pages for code splitting
const HomePage = lazy(() => import('./pages/HomePage'))
const HistoryPage = lazy(() => import('./pages/HistoryPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const SharePage = lazy(() => import('./pages/SharePage'))
const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import('./pages/RegisterPage').then(m => ({ default: m.RegisterPage })))

// Settings sub-pages
const ProvidersSettings = lazy(() => import('./pages/settings/ProvidersSettings'))
const ConnectorsSettings = lazy(() => import('./pages/settings/ConnectorsSettings'))
const MCPSettings = lazy(() => import('./pages/settings/MCPSettings'))

// Loading fallback
function PageLoader() {
  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-muted-foreground text-[14px]">Loading...</div>
    </div>
  )
}

// Placeholder for settings pages not yet implemented
function PlaceholderSettings({ title }: { title: string }) {
  return (
    <div className="max-w-2xl mx-auto p-8">
      <h2 className="text-xl font-medium text-foreground mb-4">{title}</h2>
      <p className="text-muted-foreground text-[14px]">
        This settings section is coming soon.
      </p>
    </div>
  )
}

// Wrap lazy components with Suspense
function withSuspense(Component: React.LazyExoticComponent<React.ComponentType>) {
  return (
    <Suspense fallback={<PageLoader />}>
      <Component />
    </Suspense>
  )
}

export const router = createBrowserRouter([
  // Public routes
  {
    path: '/share/:token',
    element: withSuspense(SharePage),
  },

  // Auth routes
  {
    path: '/login',
    element: (
      <AuthLayout>
        <Suspense fallback={<PageLoader />}>
          <LoginPage />
        </Suspense>
      </AuthLayout>
    ),
  },
  {
    path: '/register',
    element: (
      <AuthLayout>
        <Suspense fallback={<PageLoader />}>
          <RegisterPage />
        </Suspense>
      </AuthLayout>
    ),
  },

  // Protected routes (main app)
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: withSuspense(HomePage),
      },
      {
        path: 'history',
        element: withSuspense(HistoryPage),
      },
      {
        path: 'settings',
        element: withSuspense(SettingsPage),
        children: [
          // general is handled by SettingsPage itself as default
          {
            path: 'general',
            element: null, // Handled by parent
          },
          {
            path: 'providers',
            element: withSuspense(ProvidersSettings),
          },
          {
            path: 'connectors',
            element: withSuspense(ConnectorsSettings),
          },
          {
            path: 'mcp',
            element: withSuspense(MCPSettings),
          },
          // Placeholder routes for future implementation
          {
            path: 'account',
            element: <PlaceholderSettings title="Account" />,
          },
          {
            path: 'privacy',
            element: <PlaceholderSettings title="Privacy" />,
          },
          {
            path: 'billing',
            element: <PlaceholderSettings title="Billing" />,
          },
          {
            path: 'usage',
            element: <PlaceholderSettings title="Usage" />,
          },
          {
            path: 'capabilities',
            element: <PlaceholderSettings title="Capabilities" />,
          },
          {
            path: 'developer',
            element: <PlaceholderSettings title="Developer" />,
          },
        ],
      },
    ],
  },

  // Catch-all redirect
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
])
