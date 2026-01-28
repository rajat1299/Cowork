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
import { useChat } from '../../hooks'

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
  const { switchTask, activeTask, resetActiveChat } = useChat()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [activeTab, setActiveTab] = useState('cowork')
  const [loadingSessionId, setLoadingSessionId] = useState<string | null>(null)

  const activeTaskId = activeTask?.id ?? null

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
    resetActiveChat()
    navigate('/')
  }

  const handleSessionClick = async (sessionId: string) => {
    setLoadingSessionId(sessionId)
    try {
      await switchTask(sessionId)
      navigate('/')
    } finally {
      setLoadingSessionId(null)
    }
  }

  const userInitial = user?.email?.charAt(0).toUpperCase() || 'U'
  const userName = user?.email?.split('@')[0] || 'User'

  return (
    <aside
      className={cn(
        'relative flex flex-col h-full',
        'bg-card/40 backdrop-blur-md',
        'border-r border-border',
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
            'text-muted-foreground hover:text-foreground',
            'rounded-lg hover:bg-secondary',
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
          <div className="flex items-center gap-1 p-1 bg-secondary rounded-xl">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex-1 py-2 px-3 rounded-lg text-[13px] font-medium',
                  'transition-all duration-200',
                  activeTab === tab.id
                    ? 'bg-accent text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
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
            'text-muted-foreground hover:text-foreground',
            'border border-border hover:border-foreground/30',
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
            <h3 className="text-[12px] font-medium text-muted-foreground uppercase tracking-wide px-2 mb-2">
              Recents
            </h3>
            {isLoading && sessions.length === 0 ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 size={16} className="animate-spin text-muted-foreground" />
              </div>
            ) : sessions.length === 0 ? (
              <p className="text-[13px] text-muted-foreground px-2">
                No sessions yet
              </p>
            ) : (
              <div className="space-y-1">
                {sessions.slice(0, 10).map((session) => (
                  <SessionItem
                    key={session.id}
                    session={session}
                    isActive={session.id === activeTaskId}
                    isLoading={session.id === loadingSessionId}
                    onClick={() => handleSessionClick(session.id)}
                  />
                ))}
                {sessions.length > 10 && (
                  <button
                    onClick={() => navigate('/history')}
                    className="w-full text-center py-2 text-[12px] text-muted-foreground hover:text-foreground transition-colors"
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
            'hover:bg-secondary',
            'transition-all duration-200',
            collapsed && 'justify-center'
          )}
        >
          <div className="w-8 h-8 rounded-full bg-burnt/15 flex items-center justify-center flex-shrink-0">
            <span className="text-[13px] font-medium text-burnt">{userInitial}</span>
          </div>
          {!collapsed && (
            <div className="flex-1 text-left">
              <span className="block text-[13px] text-foreground truncate">{userName}</span>
              <span className="block text-[11px] text-muted-foreground">Free plan</span>
            </div>
          )}
        </button>

        {/* User menu dropdown */}
        {showUserMenu && !collapsed && (
          <div
            className={cn(
              'absolute bottom-full left-3 right-3 mb-2',
              'bg-card border border-border rounded-xl',
              'shadow-lg shadow-black/20',
              'py-1 animate-scale-in origin-bottom'
            )}
          >
            <MenuItem icon={User} label="Profile" onClick={() => navigate('/settings')} />
            <MenuItem icon={Clock} label="History" onClick={() => navigate('/history')} />
            <MenuItem icon={Settings} label="Settings" onClick={() => navigate('/settings')} />
            <div className="h-px bg-border my-1" />
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
      className="w-full flex items-center gap-3 px-3 py-2 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
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
  isLoading?: boolean
  onClick: () => void
}

function SessionItem({ session, isActive, isLoading, onClick }: SessionItemProps) {
  return (
    <button
      onClick={onClick}
      disabled={isLoading}
      className={cn(
        'w-full flex items-start gap-2 px-2 py-2 rounded-lg text-left',
        'transition-all duration-200',
        isActive
          ? 'bg-secondary text-foreground'
          : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50',
        isLoading && 'opacity-70'
      )}
    >
      {isLoading ? (
        <Loader2
          size={14}
          strokeWidth={1.5}
          className="mt-0.5 flex-shrink-0 animate-spin text-burnt"
        />
      ) : (
        <MessageSquare
          size={14}
          strokeWidth={1.5}
          className={cn(
            'mt-0.5 flex-shrink-0',
            session.status === 'ongoing' ? 'text-burnt' : 'text-muted-foreground'
          )}
        />
      )}
      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-medium truncate">{session.title}</p>
        <p className="text-[11px] text-muted-foreground truncate">
          {formatRelativeTime(session.updatedAt)}
        </p>
      </div>
    </button>
  )
}
