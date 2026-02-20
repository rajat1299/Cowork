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
const CapabilitiesSettings = lazy(() => import('./pages/settings/CapabilitiesSettings'))

// Loading fallback
// eslint-disable-next-line react-refresh/only-export-components
function PageLoader() {
  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-muted-foreground text-[14px]">Loading...</div>
    </div>
  )
}

// Coming soon descriptions for settings pages not yet implemented
const SETTINGS_DESCRIPTIONS: Record<string, { description: string; features: string[] }> = {
  Account: {
    description: 'Manage your profile, email, and account preferences.',
    features: ['Update display name and avatar', 'Change email address', 'Delete account'],
  },
  Privacy: {
    description: 'Control how your data is stored and used.',
    features: ['Manage conversation history retention', 'Data export and deletion', 'Analytics opt-out'],
  },
  Billing: {
    description: 'View your plan details and manage payment methods.',
    features: ['Current plan overview', 'Payment method management', 'Invoice history'],
  },
  Usage: {
    description: 'Monitor your API usage, token consumption, and costs.',
    features: ['Token usage by model', 'Request history and trends', 'Cost breakdown'],
  },
  Developer: {
    description: 'Access API keys, webhooks, and developer tools.',
    features: ['Personal API keys', 'Webhook configuration', 'Debug logs'],
  },
}

// eslint-disable-next-line react-refresh/only-export-components
function PlaceholderSettings({ title }: { title: string }) {
  const info = SETTINGS_DESCRIPTIONS[title]
  return (
    <div className="max-w-2xl mx-auto p-8">
      <h2 className="text-xl font-medium text-foreground mb-2">{title}</h2>
      <p className="text-muted-foreground text-[14px] mb-6">
        {info?.description ?? 'This settings section is coming soon.'}
      </p>
      {info?.features && (
        <div className="rounded-xl border border-border bg-secondary/30 p-5">
          <p className="text-[13px] font-medium text-foreground mb-3">Coming soon</p>
          <ul className="space-y-2">
            {info.features.map((feature) => (
              <li key={feature} className="flex items-center gap-2 text-[13px] text-muted-foreground">
                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40 flex-shrink-0" />
                {feature}
              </li>
            ))}
          </ul>
        </div>
      )}
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
            element: withSuspense(CapabilitiesSettings),
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
