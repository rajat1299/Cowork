import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Plus,
  PanelLeftClose,
  PanelLeft,
  Settings,
  Clock,
  LogOut,
  User,
  MessageSquare,
  Loader2,
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { useAuthStore } from '../../stores/authStore'
import { useSessionStore, formatRelativeTime } from '../../stores/sessionStore'
import { useChatStore } from '../../stores/chatStore'

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
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const { sessions, isLoading, fetchSessions } = useSessionStore()
  const { setActiveTask, activeTaskId } = useChatStore()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [activeTab, setActiveTab] = useState('cowork')

  // Fetch sessions on mount
  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const handleNewTask = () => {
    // Clear active task and navigate home to start fresh
    setActiveTask(null)
    navigate('/')
  }

  const handleSessionClick = (sessionId: string) => {
    setActiveTask(sessionId)
    navigate('/')
  }

  const userInitial = user?.email?.charAt(0).toUpperCase() || 'U'
  const userName = user?.email?.split('@')[0] || 'User'

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
          onClick={handleNewTask}
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
            {isLoading && sessions.length === 0 ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 size={16} className="animate-spin text-ink-subtle" />
              </div>
            ) : sessions.length === 0 ? (
              <p className="text-[13px] text-ink-subtle px-2">
                No sessions yet
              </p>
            ) : (
              <div className="space-y-1">
                {sessions.slice(0, 10).map((session) => (
                  <SessionItem
                    key={session.id}
                    session={session}
                    isActive={session.id === activeTaskId}
                    onClick={() => handleSessionClick(session.id)}
                  />
                ))}
                {sessions.length > 10 && (
                  <button
                    onClick={() => navigate('/history')}
                    className="w-full text-center py-2 text-[12px] text-ink-subtle hover:text-ink transition-colors"
                  >
                    View all ({sessions.length})
                  </button>
                )}
              </div>
            )}
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
            <span className="text-[13px] font-medium text-burnt">{userInitial}</span>
          </div>
          {!collapsed && (
            <div className="flex-1 text-left">
              <span className="block text-[13px] text-ink truncate">{userName}</span>
              <span className="block text-[11px] text-ink-subtle">Free plan</span>
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
            <MenuItem icon={User} label="Profile" onClick={() => navigate('/settings')} />
            <MenuItem icon={Clock} label="History" onClick={() => navigate('/history')} />
            <MenuItem icon={Settings} label="Settings" onClick={() => navigate('/settings')} />
            <div className="h-px bg-dark-border my-1" />
            <MenuItem icon={LogOut} label="Sign out" onClick={handleLogout} />
          </div>
        )}
      </div>
    </aside>
  )
}

interface MenuItemProps {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number }>
  label: string
  onClick?: () => void
}

function MenuItem({ icon: Icon, label, onClick }: MenuItemProps) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2 text-ink-muted hover:text-ink hover:bg-dark-elevated transition-colors"
    >
      <Icon size={15} strokeWidth={1.5} />
      <span className="text-[13px]">{label}</span>
    </button>
  )
}

// ============ Session Item Component ============

interface SessionItemProps {
  session: {
    id: string
    title: string
    preview: string
    status: 'ongoing' | 'completed'
    updatedAt: string
  }
  isActive: boolean
  onClick: () => void
}

function SessionItem({ session, isActive, onClick }: SessionItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-start gap-2 px-2 py-2 rounded-lg text-left',
        'transition-all duration-200',
        isActive
          ? 'bg-dark-surface text-ink'
          : 'text-ink-muted hover:text-ink hover:bg-dark-surface/50'
      )}
    >
      <MessageSquare
        size={14}
        strokeWidth={1.5}
        className={cn(
          'mt-0.5 flex-shrink-0',
          session.status === 'ongoing' ? 'text-burnt' : 'text-ink-subtle'
        )}
      />
      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-medium truncate">{session.title}</p>
        <p className="text-[11px] text-ink-subtle truncate">
          {formatRelativeTime(session.updatedAt)}
        </p>
      </div>
    </button>
  )
}
