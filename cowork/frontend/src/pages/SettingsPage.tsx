import { NavLink, Outlet } from 'react-router-dom'
import { Key, Plug, Box } from 'lucide-react'
import { cn } from '../lib/utils'

const settingsNav = [
  { path: 'providers', label: 'Providers', icon: Key, description: 'API keys & models' },
  { path: 'connectors', label: 'Connectors', icon: Plug, description: 'Integrations' },
  { path: 'mcp', label: 'MCP Servers', icon: Box, description: 'Model Context Protocol' },
]

/**
 * Settings page layout with sub-navigation
 */
export default function SettingsPage() {
  return (
    <div className="h-full flex">
      {/* Settings nav sidebar */}
      <div className="w-64 border-r border-dark-border p-4">
        <h1 className="text-lg font-medium text-ink mb-6 px-2">Settings</h1>
        <nav className="space-y-1">
          {settingsNav.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-xl',
                  'transition-colors',
                  isActive
                    ? 'bg-dark-surface text-ink'
                    : 'text-ink-muted hover:text-ink hover:bg-dark-surface/50'
                )
              }
            >
              <item.icon size={18} strokeWidth={1.5} />
              <div>
                <div className="text-[14px] font-medium">{item.label}</div>
                <div className="text-[11px] text-ink-subtle">{item.description}</div>
              </div>
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Settings content */}
      <div className="flex-1 overflow-y-auto">
        <Outlet />
      </div>
    </div>
  )
}
