import { useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { 
  User, 
  Key, 
  Plug, 
  Box, 
  Shield, 
  CreditCard,
  BarChart3,
  Sparkles,
  Code,
} from 'lucide-react'
import { cn } from '../lib/utils'
import { useAuthStore } from '../stores/authStore'
import { useThemeStore } from '../stores/themeStore'

// Settings navigation structure - grouped like Claude's settings
const settingsGroups = [
  {
    items: [
      { path: 'general', label: 'General', icon: User },
      { path: 'account', label: 'Account', icon: Shield },
      { path: 'privacy', label: 'Privacy', icon: Shield },
      { path: 'billing', label: 'Billing', icon: CreditCard },
      { path: 'usage', label: 'Usage', icon: BarChart3 },
      { path: 'capabilities', label: 'Capabilities', icon: Sparkles },
      { path: 'connectors', label: 'Connectors', icon: Plug },
    ],
  },
  {
    title: 'Desktop app',
    items: [
      { path: 'providers', label: 'Providers', icon: Key },
      { path: 'mcp', label: 'MCP Servers', icon: Box },
      { path: 'developer', label: 'Developer', icon: Code },
    ],
  },
]

/**
 * Settings page layout with Claude-like sub-navigation
 */
export default function SettingsPage() {
  const location = useLocation()

  // Show GeneralSettings for /settings, /settings/, or /settings/general
  const isGeneralRoute =
    location.pathname === '/settings' ||
    location.pathname === '/settings/' ||
    location.pathname === '/settings/general'

  return (
    <div className="h-full flex">
      {/* Settings nav sidebar */}
      <div className="w-56 border-r border-border py-6 px-4 overflow-y-auto">
        <h1 className="text-xl font-medium text-foreground mb-6 px-2">Settings</h1>
        
        {settingsGroups.map((group, groupIndex) => (
          <div key={groupIndex} className={cn(groupIndex > 0 && 'mt-6')}>
            {group.title && (
              <h2 className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide px-2 mb-2">
                {group.title}
              </h2>
            )}
            <nav className="space-y-0.5">
              {group.items.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-2.5 px-3 py-2 rounded-lg',
                      'transition-colors text-[14px]',
                      (isActive || (isGeneralRoute && item.path === 'general'))
                        ? 'bg-secondary text-foreground'
                        : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
                    )
                  }
                >
                  <item.icon size={16} strokeWidth={1.5} />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </nav>
          </div>
        ))}
      </div>

      {/* Settings content */}
      <div className="flex-1 overflow-y-auto">
        {isGeneralRoute ? <GeneralSettings /> : <Outlet />}
      </div>
    </div>
  )
}

/**
 * General/Profile settings - default view
 */
function GeneralSettings() {
  const { user, updateUserName } = useAuthStore()
  const { mode, setMode } = useThemeStore()

  // Get user display info
  const userEmail = user?.email || ''
  const defaultName = userEmail.split('@')[0] || ''
  const savedName = user?.name || defaultName
  const userInitial = (savedName || defaultName).charAt(0).toUpperCase() || 'U'

  // Local state for form fields
  const [fullName, setFullName] = useState(savedName)
  const [nickname, setNickname] = useState(savedName.split('.')[0] || savedName)

  // Sync local state when store hydrates from localStorage
  useEffect(() => {
    setFullName(savedName)
    setNickname(savedName.split('.')[0] || savedName)
  }, [savedName])

  // Save name when input loses focus
  const handleNameBlur = () => {
    if (fullName.trim() && fullName !== user?.name) {
      updateUserName(fullName.trim())
    }
  }
  
  return (
    <div className="max-w-2xl mx-auto p-8">
      <h2 className="text-xl font-medium text-foreground mb-8">Profile</h2>
      
      {/* Profile section */}
      <section className="mb-10">
        <div className="grid grid-cols-2 gap-6">
          {/* Full name */}
          <div>
            <label className="block text-[13px] text-muted-foreground mb-2">Full name</label>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-burnt/15 flex items-center justify-center">
                <span className="text-sm font-medium text-burnt">{userInitial}</span>
              </div>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                onBlur={handleNameBlur}
                placeholder="Your name"
                className={cn(
                  'flex-1 px-3 py-2.5 rounded-xl',
                  'bg-secondary border border-border',
                  'text-foreground text-[14px] placeholder:text-muted-foreground',
                  'focus:outline-none focus:border-burnt/50'
                )}
              />
            </div>
          </div>
          
          {/* What Claude calls you */}
          <div>
            <label className="block text-[13px] text-muted-foreground mb-2">What should Cowork call you?</label>
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="Nickname"
              className={cn(
                'w-full px-3 py-2.5 rounded-xl',
                'bg-secondary border border-border',
                'text-foreground text-[14px] placeholder:text-muted-foreground',
                'focus:outline-none focus:border-burnt/50'
              )}
            />
          </div>
        </div>
        
        {/* Work function */}
        <div className="mt-6">
          <label className="block text-[13px] text-muted-foreground mb-2">What best describes your work?</label>
          <select
            className={cn(
              'w-full px-3 py-2.5 rounded-xl',
              'bg-secondary border border-border',
              'text-foreground text-[14px]',
              'focus:outline-none focus:border-burnt/50'
            )}
          >
            <option value="">Select your work function</option>
            <option value="engineering">Software Engineering</option>
            <option value="design">Design</option>
            <option value="product">Product Management</option>
            <option value="data">Data Science</option>
            <option value="research">Research</option>
            <option value="other">Other</option>
          </select>
        </div>
        
        {/* Personal preferences */}
        <div className="mt-6">
          <label className="block text-[13px] text-muted-foreground mb-1">
            What personal preferences should Cowork consider in responses?
          </label>
          <p className="text-[12px] text-muted-foreground mb-2">
            Your preferences will apply to all conversations.
          </p>
          <textarea
            rows={3}
            placeholder="e.g., when learning new concepts, I find analogies particularly helpful"
            className={cn(
              'w-full px-3 py-2.5 rounded-xl resize-none',
              'bg-secondary border border-border',
              'text-foreground text-[14px] placeholder:text-muted-foreground',
              'focus:outline-none focus:border-burnt/50'
            )}
          />
        </div>
      </section>
      
      {/* Notifications section */}
      <section className="mb-10">
        <h3 className="text-lg font-medium text-foreground mb-4">Notifications</h3>
        
        <div className="space-y-4">
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-[14px] text-foreground">Response completions</p>
              <p className="text-[12px] text-muted-foreground">
                Get notified when Cowork has finished a response
              </p>
            </div>
            <ToggleSwitch />
          </div>
          
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-[14px] text-foreground">Email updates</p>
              <p className="text-[12px] text-muted-foreground">
                Get an email when Cowork needs your response
              </p>
            </div>
            <ToggleSwitch />
          </div>
        </div>
      </section>
      
      {/* Appearance section */}
      <section>
        <h3 className="text-lg font-medium text-foreground mb-4">Appearance</h3>
        
        <div>
          <label className="block text-[13px] text-muted-foreground mb-3">Color mode</label>
          <div className="flex gap-3">
            <ThemeOption 
              label="System" 
              active={mode === 'system'} 
              onClick={() => setMode('system')}
            />
            <ThemeOption 
              label="Light" 
              active={mode === 'light'} 
              onClick={() => setMode('light')}
            />
            <ThemeOption 
              label="Dark" 
              active={mode === 'dark'} 
              onClick={() => setMode('dark')}
            />
          </div>
        </div>
      </section>
    </div>
  )
}

/**
 * Toggle switch component
 */
function ToggleSwitch({ enabled = false }: { enabled?: boolean }) {
  return (
    <button
      className={cn(
        'relative w-11 h-6 rounded-full transition-colors',
        enabled ? 'bg-burnt' : 'bg-secondary border border-border'
      )}
    >
      <span
        className={cn(
          'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
          enabled ? 'left-6' : 'left-1'
        )}
      />
    </button>
  )
}

/**
 * Theme option button
 */
interface ThemeOptionProps {
  label: string
  active?: boolean
  onClick?: () => void
}

function ThemeOption({ label, active = false, onClick }: ThemeOptionProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex flex-col items-center gap-2 p-3 rounded-xl border transition-all',
        active
          ? 'border-burnt bg-burnt/10 ring-2 ring-burnt/20'
          : 'border-border hover:border-foreground/30 hover:bg-secondary/30'
      )}
    >
      <div className={cn(
        'w-20 h-14 rounded-lg overflow-hidden',
        label === 'Dark' ? 'bg-[#1C1C1C]' : label === 'Light' ? 'bg-[#F5E8D8]' : 'bg-gradient-to-b from-[#F5E8D8] to-[#1C1C1C]'
      )}>
        {/* Mini preview */}
        <div className="w-full h-full rounded-lg flex items-end p-1.5">
          <div className={cn(
            'w-full h-2.5 rounded',
            'bg-burnt/80'
          )} />
        </div>
      </div>
      <span className={cn(
        'text-[13px] font-medium',
        active ? 'text-burnt' : 'text-muted-foreground'
      )}>
        {label}
      </span>
    </button>
  )
}
