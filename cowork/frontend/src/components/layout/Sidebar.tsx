import { useState } from 'react'
import {
  Plus,
  PanelLeftClose,
  PanelLeft,
  Settings,
  Clock,
  LogOut,
  User,
} from 'lucide-react'
import { cn } from '../../lib/utils'

interface SidebarProps {
  collapsed?: boolean
  onToggle?: () => void
}

// Tabs for the top navigation
const tabs = [
  { id: 'chat', label: 'Chat' },
  { id: 'cowork', label: 'Cowork', active: true },
  { id: 'code', label: 'Code' },
]

export function Sidebar({ collapsed = false, onToggle }: SidebarProps) {
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [activeTab, setActiveTab] = useState('cowork')

  return (
    <aside
      className={cn(
        'relative flex flex-col h-full',
        'bg-dark-bg',
        'border-r border-dark-border',
        'transition-all duration-300 ease-smooth',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Toggle button */}
      <div className="flex items-center p-3">
        <button
          onClick={onToggle}
          className={cn(
            'w-8 h-8 flex items-center justify-center',
            'text-ink-subtle hover:text-ink',
            'rounded-lg hover:bg-dark-surface',
            'transition-all duration-200'
          )}
        >
          {collapsed ? (
            <PanelLeft size={18} strokeWidth={1.5} />
          ) : (
            <PanelLeftClose size={18} strokeWidth={1.5} />
          )}
        </button>
      </div>

      {/* Tab navigation */}
      {!collapsed && (
        <div className="px-3 mb-4">
          <div className="flex items-center gap-1 p-1 bg-dark-surface rounded-xl">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex-1 py-2 px-3 rounded-lg text-[13px] font-medium',
                  'transition-all duration-200',
                  activeTab === tab.id
                    ? 'bg-dark-elevated text-ink'
                    : 'text-ink-subtle hover:text-ink'
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* New task button */}
      <div className="px-3 mb-4">
        <button
          className={cn(
            'flex items-center justify-center gap-2 h-10 w-full',
            'text-ink-muted hover:text-ink',
            'border border-dark-border hover:border-ink-faint',
            'rounded-xl',
            'transition-all duration-200',
            collapsed && 'w-10 mx-auto'
          )}
        >
          <Plus size={16} strokeWidth={1.5} />
          {!collapsed && <span className="text-[13px]">New task</span>}
        </button>
      </div>

      {/* Recents section */}
      <nav className="flex-1 px-3 overflow-y-auto scrollbar-hide">
        {!collapsed && (
          <div>
            <h3 className="text-[12px] font-medium text-ink-subtle uppercase tracking-wide px-2 mb-2">
              Recents
            </h3>
            <p className="text-[13px] text-ink-subtle px-2">
              No sessions yet
            </p>
          </div>
        )}
      </nav>

      {/* Bottom: User */}
      <div className="relative p-3">
        <button
          onClick={() => setShowUserMenu(!showUserMenu)}
          className={cn(
            'w-full flex items-center gap-3 p-2 rounded-xl',
            'hover:bg-dark-surface',
            'transition-all duration-200',
            collapsed && 'justify-center'
          )}
        >
          <div className="w-8 h-8 rounded-full bg-burnt/15 flex items-center justify-center flex-shrink-0">
            <span className="text-[13px] font-medium text-burnt">R</span>
          </div>
          {!collapsed && (
            <div className="flex-1 text-left">
              <span className="block text-[13px] text-ink">Rajat Tiwari</span>
              <span className="block text-[11px] text-ink-subtle">Pro plan</span>
            </div>
          )}
        </button>

        {/* User menu dropdown */}
        {showUserMenu && !collapsed && (
          <div
            className={cn(
              'absolute bottom-full left-3 right-3 mb-2',
              'bg-dark-surface border border-dark-border rounded-xl',
              'shadow-lg shadow-black/20',
              'py-1 animate-scale-in origin-bottom'
            )}
          >
            <MenuItem icon={User} label="Profile" />
            <MenuItem icon={Clock} label="History" />
            <MenuItem icon={Settings} label="Settings" />
            <div className="h-px bg-dark-border my-1" />
            <MenuItem icon={LogOut} label="Sign out" />
          </div>
        )}
      </div>
    </aside>
  )
}

function MenuItem({ icon: Icon, label }: { icon: React.ComponentType<{ size?: number; strokeWidth?: number }>; label: string }) {
  return (
    <button className="w-full flex items-center gap-3 px-3 py-2 text-ink-muted hover:text-ink hover:bg-dark-elevated transition-colors">
      <Icon size={15} strokeWidth={1.5} />
      <span className="text-[13px]">{label}</span>
    </button>
  )
}
