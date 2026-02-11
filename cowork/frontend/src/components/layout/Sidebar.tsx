import { useState, useEffect, memo, useCallback, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  Plus,
  PanelLeftClose,
  PanelLeft,
  Settings,
  Clock,
  LogOut,
  Loader2,
  MoreHorizontal,
  Star,
  Pencil,
  Trash2,
  HelpCircle,
  ExternalLink,
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { useAuthStore } from '../../stores/authStore'
import { useSessionStore, formatRelativeTime } from '../../stores/sessionStore'
import { useChatStore } from '../../stores/chatStore'
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

function buildRecentsFingerprint(state: ReturnType<typeof useChatStore.getState>): string {
  const taskBits = Object.values(state.tasks)
    .map((task) => {
      const userTurns = task.messages.filter((message) => message.role === 'user').length
      return `${task.id}:${task.status}:${userTurns}:${task.endTime || 0}`
    })
    .sort()
  return `${state.activeTaskId || 'none'}|${taskBits.join('|')}`
}

export function Sidebar({ collapsed = false, onToggle }: SidebarProps) {
  const navigate = useNavigate()
  // Use individual selectors to avoid unnecessary re-renders
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const sessions = useSessionStore((s) => s.sessions)
  const isLoading = useSessionStore((s) => s.isLoading)
  const fetchSessions = useSessionStore((s) => s.fetchSessions)
  const syncLocalSessions = useSessionStore((s) => s.syncLocalSessions)
  const refreshSessionsBackground = useSessionStore((s) => s.refreshSessionsBackground)
  const { switchTask, activeTask, resetActiveChat } = useChat()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [activeTab, setActiveTab] = useState('cowork')
  const [loadingSessionId, setLoadingSessionId] = useState<string | null>(null)
  const userMenuRef = useRef<HTMLDivElement>(null)

  const activeTaskId = activeTask?.id ?? null

  // Close user menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false)
      }
    }
    if (showUserMenu) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showUserMenu])

  // Fetch sessions on mount
  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  useEffect(() => {
    let previousFingerprint = buildRecentsFingerprint(useChatStore.getState())
    const unsubscribe = useChatStore.subscribe((state) => {
      const nextFingerprint = buildRecentsFingerprint(state)
      if (nextFingerprint === previousFingerprint) return
      previousFingerprint = nextFingerprint
      syncLocalSessions()
      void refreshSessionsBackground()
    })

    return () => unsubscribe()
  }, [refreshSessionsBackground, syncLocalSessions])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const handleNewTask = () => {
    // Clear active task and navigate home to start fresh
    resetActiveChat()
    navigate('/')
  }

  const handleSessionClick = useCallback(async (sessionId: string) => {
    setLoadingSessionId(sessionId)
    try {
      await switchTask(sessionId)
      navigate('/')
    } finally {
      setLoadingSessionId(null)
    }
  }, [switchTask, navigate])

  const userName = user?.name || user?.email?.split('@')[0] || 'User'
  const userInitial = userName.charAt(0).toUpperCase()

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
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
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
      <div ref={userMenuRef} className="relative p-3">
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
            <MenuItem icon={Settings} label="Settings" to="/settings" />
            <MenuItem icon={Clock} label="History" to="/history" />
            <div className="h-px bg-border my-1 mx-3" />
            <MenuItem icon={HelpCircle} label="Get help" to="/help" />
            <MenuItem icon={ExternalLink} label="Learn more" to="/about" />
            <div className="h-px bg-border my-1 mx-3" />
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
  to?: string
}

function MenuItem({ icon: Icon, label, onClick, to }: MenuItemProps) {
  const baseClasses = cn(
    'w-full flex items-center gap-2.5 px-2 py-1.5 rounded-md',
    'text-muted-foreground hover:text-foreground hover:bg-accent',
    'transition-colors duration-150'
  )

  if (to) {
    return (
      <div className="px-1.5">
        <Link to={to} className={baseClasses}>
          <Icon size={15} strokeWidth={1.5} />
          <span className="text-[13px]">{label}</span>
        </Link>
      </div>
    )
  }

  return (
    <div className="px-1.5">
      <button onClick={onClick} className={baseClasses}>
        <Icon size={15} strokeWidth={1.5} />
        <span className="text-[13px]">{label}</span>
      </button>
    </div>
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

const SessionItem = memo(function SessionItem({ session, isActive, isLoading, onClick }: SessionItemProps) {
  const [isHovered, setIsHovered] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false)
      }
    }
    if (showMenu) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showMenu])

  const handleMenuClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setShowMenu(!showMenu)
  }

  const handleAction = (action: 'star' | 'rename' | 'delete', e: React.MouseEvent) => {
    e.stopPropagation()
    setShowMenu(false)
    // TODO: Implement actions
    console.log(`${action} session:`, session.id)
  }

  const showMenuButton = isHovered || isActive || showMenu

  return (
    <div
      className="relative"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false)
        if (!showMenu) setShowMenu(false)
      }}
    >
      <button
        onClick={onClick}
        disabled={isLoading}
        className={cn(
          'w-full flex items-center gap-2 px-2 py-2 rounded-lg text-left',
          'transition-all duration-200',
          isActive
            ? 'bg-secondary text-foreground'
            : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50',
          isLoading && 'opacity-70'
        )}
      >
        {isLoading && (
          <Loader2
            size={14}
            strokeWidth={1.5}
            className="flex-shrink-0 animate-spin text-burnt"
          />
        )}
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-medium truncate">{session.title}</p>
          <p className="text-[11px] text-muted-foreground truncate">
            {formatRelativeTime(session.updatedAt)}
          </p>
        </div>

        {/* More options button */}
        <div
          className={cn(
            'flex-shrink-0 transition-opacity duration-150',
            showMenuButton ? 'opacity-100' : 'opacity-0'
          )}
        >
          <div
            role="button"
            tabIndex={0}
            onClick={handleMenuClick}
            onKeyDown={(e) => e.key === 'Enter' && handleMenuClick(e as unknown as React.MouseEvent)}
            className={cn(
              'w-6 h-6 flex items-center justify-center rounded-md',
              'hover:bg-accent',
              'transition-colors duration-150',
              showMenu && 'bg-accent'
            )}
          >
            <MoreHorizontal size={14} strokeWidth={1.5} />
          </div>
        </div>
      </button>

      {/* Dropdown menu */}
      {showMenu && (
        <div
          ref={menuRef}
          className={cn(
            'absolute right-0 top-full mt-1 z-50',
            'min-w-[140px] py-1',
            'bg-popover border border-border rounded-lg',
            'shadow-lg shadow-black/20',
            'animate-scale-in'
          )}
        >
          <SessionMenuItem
            icon={Star}
            label="Star"
            onClick={(e) => handleAction('star', e)}
          />
          <SessionMenuItem
            icon={Pencil}
            label="Rename"
            onClick={(e) => handleAction('rename', e)}
          />
          <div className="h-px bg-border my-1 mx-3" />
          <SessionMenuItem
            icon={Trash2}
            label="Delete"
            onClick={(e) => handleAction('delete', e)}
            variant="destructive"
          />
        </div>
      )}
    </div>
  )
})

// ============ Session Menu Item Component ============

interface SessionMenuItemProps {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>
  label: string
  onClick: (e: React.MouseEvent) => void
  variant?: 'default' | 'destructive'
}

function SessionMenuItem({ icon: Icon, label, onClick, variant = 'default' }: SessionMenuItemProps) {
  return (
    <div className="px-1.5">
      <button
        onClick={onClick}
        className={cn(
          'w-full flex items-center gap-2.5 px-2 py-1.5 rounded-md',
          'text-[13px] text-left',
          'transition-colors duration-150',
          variant === 'destructive'
            ? 'text-red-400 hover:text-red-300 hover:bg-red-500/10'
            : 'text-muted-foreground hover:text-foreground hover:bg-accent'
        )}
      >
        <Icon size={14} strokeWidth={1.5} className="flex-shrink-0" />
        <span>{label}</span>
      </button>
    </div>
  )
}
