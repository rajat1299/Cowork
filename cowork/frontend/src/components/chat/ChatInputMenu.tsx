import { useState, useRef, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Image, Camera, Globe, Plug, ChevronRight, Settings2 } from 'lucide-react'
import { cn } from '../../lib/utils'
import { useConnectors } from '../../hooks/useConnectors'

// Popular connectors to show when user has no configured connectors
const POPULAR_CONNECTORS = [
  'github',
  'slack',
  'google_gmail_mcp',
  'google_calendar',
  'google_drive_mcp',
  'notion',
  'twitter',
  'linkedin',
]

interface ChatInputMenuProps {
  isOpen: boolean
  onClose: () => void
  searchEnabled: boolean
  onSearchToggle: () => void
  onScreenshot: () => void
  onAddFiles: () => void
  onAddConnector?: (connectorId: string, connectorName: string) => void
}

export function ChatInputMenu({
  isOpen,
  onClose,
  searchEnabled,
  onSearchToggle,
  onScreenshot,
  onAddFiles,
  onAddConnector,
}: ChatInputMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const { groups, configs, isLoading, fetchConfigsForGroup } = useConnectors()
  const [showConnectorSubmenu, setShowConnectorSubmenu] = useState(false)
  const submenuTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Fetch configs for all groups to check which are configured
  useEffect(() => {
    if (isOpen && groups.length > 0) {
      groups.forEach((group) => {
        if (!configs[group.id]) {
          fetchConfigsForGroup(group.id)
        }
      })
    }
  }, [isOpen, groups, configs, fetchConfigsForGroup])

  // Determine which connectors to show
  const connectorsToShow = useMemo(() => {
    // Find configured connectors (those with at least one config value)
    const configuredIds = Object.entries(configs)
      .filter(([, configList]) => configList && configList.length > 0)
      .map(([groupId]) => groupId)

    if (configuredIds.length > 0) {
      // Show only configured connectors
      return groups.filter((g) => configuredIds.includes(g.id))
    } else {
      // Show popular connectors
      return groups
        .filter((g) => POPULAR_CONNECTORS.includes(g.id))
        .sort((a, b) => POPULAR_CONNECTORS.indexOf(a.id) - POPULAR_CONNECTORS.indexOf(b.id))
    }
  }, [groups, configs])

  // Close menu on outside click
  useEffect(() => {
    if (!isOpen) return

    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }

    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside)
    }, 0)

    return () => {
      clearTimeout(timer)
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen, onClose])

  // Close on escape
  useEffect(() => {
    if (!isOpen) return

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (submenuTimeoutRef.current) {
        clearTimeout(submenuTimeoutRef.current)
      }
    }
  }, [])

  // Reset submenu when menu closes
  const [prevIsOpen, setPrevIsOpen] = useState(isOpen)
  if (prevIsOpen !== isOpen) {
    setPrevIsOpen(isOpen)
    if (!isOpen) {
      setShowConnectorSubmenu(false)
    }
  }

  if (!isOpen) return null

  const handleManageConnectors = () => {
    onClose()
    navigate('/settings/connectors')
  }

  const handleConnectorClick = (connectorId: string, connectorName: string) => {
    onAddConnector?.(connectorId, connectorName)
    onClose()
  }

  const handleConnectorMouseEnter = () => {
    if (submenuTimeoutRef.current) {
      clearTimeout(submenuTimeoutRef.current)
    }
    setShowConnectorSubmenu(true)
  }

  const handleConnectorMouseLeave = () => {
    submenuTimeoutRef.current = setTimeout(() => {
      setShowConnectorSubmenu(false)
    }, 150)
  }

  return (
    <div
      ref={menuRef}
      className={cn(
        'absolute bottom-full left-0 mb-2 z-50',
        'min-w-[200px] py-1',
        'bg-card border border-border rounded-xl',
        'shadow-lg shadow-black/20',
        'animate-in fade-in-0 zoom-in-95 duration-150'
      )}
    >
      {/* Add files or photos */}
      <MenuItem
        icon={Image}
        label="Add files or photos"
        onClick={() => {
          onAddFiles()
          onClose()
        }}
      />

      {/* Take a screenshot */}
      <MenuItem
        icon={Camera}
        label="Take a screenshot"
        onClick={() => {
          onScreenshot()
          onClose()
        }}
      />

      {/* Web search toggle */}
      <MenuToggleItem
        icon={Globe}
        label="Web search"
        checked={searchEnabled}
        onClick={onSearchToggle}
      />

      {/* Divider */}
      <div className="h-px bg-border my-1" />

      {/* Add connectors - with submenu */}
      <div
        className="relative"
        onMouseEnter={handleConnectorMouseEnter}
        onMouseLeave={handleConnectorMouseLeave}
      >
        <button
          className={cn(
            'w-full flex items-center gap-3 px-3 py-2',
            'text-[13px] text-muted-foreground',
            'hover:bg-accent hover:text-foreground',
            'transition-colors'
          )}
        >
          <Plug size={16} strokeWidth={1.5} />
          <span className="flex-1 text-left">Add connectors</span>
          <ChevronRight size={14} strokeWidth={1.5} />
        </button>

        {/* Connector submenu - positioned to the right and upward */}
        {showConnectorSubmenu && (
          <div
            className={cn(
              'absolute left-full bottom-0 ml-1 z-50',
              'min-w-[200px] max-h-[320px] overflow-y-auto py-1',
              'bg-card border border-border rounded-xl',
              'shadow-lg shadow-black/20',
              'animate-in fade-in-0 slide-in-from-left-2 duration-150'
            )}
            onMouseEnter={handleConnectorMouseEnter}
            onMouseLeave={handleConnectorMouseLeave}
          >
            {isLoading ? (
              <div className="px-3 py-2 text-[13px] text-muted-foreground">
                Loading...
              </div>
            ) : connectorsToShow.length === 0 ? (
              <div className="px-3 py-2 text-[13px] text-muted-foreground">
                No connectors available
              </div>
            ) : (
              <>
                {connectorsToShow.map((group) => (
                  <ConnectorMenuItem
                    key={group.id}
                    id={group.id}
                    name={group.name}
                    onClick={() => handleConnectorClick(group.id, group.name)}
                  />
                ))}
              </>
            )}

            {/* Divider */}
            <div className="h-px bg-border my-1" />

            {/* Manage connectors - navigates to settings */}
            <button
              onClick={handleManageConnectors}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2',
                'text-[13px] text-muted-foreground',
                'hover:bg-accent hover:text-foreground',
                'transition-colors'
              )}
            >
              <Settings2 size={16} strokeWidth={1.5} />
              <span>Manage connectors</span>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ============ Menu Item Components ============

interface MenuItemProps {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>
  label: string
  onClick: () => void
}

function MenuItem({ icon: Icon, label, onClick }: MenuItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-3 py-2',
        'text-[13px] text-muted-foreground',
        'hover:bg-accent hover:text-foreground',
        'transition-colors'
      )}
    >
      <Icon size={16} strokeWidth={1.5} />
      <span>{label}</span>
    </button>
  )
}

interface MenuToggleItemProps {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>
  label: string
  checked: boolean
  onClick: () => void
}

function MenuToggleItem({ icon: Icon, label, checked, onClick }: MenuToggleItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-3 py-2',
        'text-[13px]',
        checked ? 'text-foreground' : 'text-muted-foreground',
        'hover:bg-accent hover:text-foreground',
        'transition-colors'
      )}
    >
      <Icon
        size={16}
        strokeWidth={1.5}
        className={cn(checked && 'text-burnt')}
      />
      <span className="flex-1 text-left">{label}</span>
      {/* Toggle indicator */}
      <div
        className={cn(
          'w-4 h-4 rounded-full border-2 flex items-center justify-center',
          'transition-colors',
          checked
            ? 'border-burnt bg-burnt'
            : 'border-muted-foreground'
        )}
      >
        {checked && (
          <svg
            width="10"
            height="10"
            viewBox="0 0 10 10"
            fill="none"
            className="text-white"
          >
            <path
              d="M2 5L4 7L8 3"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </div>
    </button>
  )
}

interface ConnectorMenuItemProps {
  id: string
  name: string
  onClick: () => void
}

function ConnectorMenuItem({ id, name, onClick }: ConnectorMenuItemProps) {
  const IconComponent = CONNECTOR_ICONS[id]

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-3 py-2',
        'text-[13px] text-muted-foreground',
        'hover:bg-accent hover:text-foreground',
        'transition-colors'
      )}
    >
      <div className="w-5 h-5 flex items-center justify-center">
        {IconComponent ? (
          <IconComponent />
        ) : (
          <div className="w-5 h-5 rounded bg-secondary flex items-center justify-center text-[10px] font-medium">
            {id.charAt(0).toUpperCase()}
          </div>
        )}
      </div>
      <span className="capitalize">{name.replace(/_/g, ' ')}</span>
    </button>
  )
}

// ============ Connector Icons ============

const CONNECTOR_ICONS: Record<string, React.ComponentType> = {
  github: GitHubIcon,
  slack: SlackIcon,
  google_gmail_mcp: GmailIcon,
  google_calendar: GoogleCalendarIcon,
  google_drive_mcp: GoogleDriveIcon,
  notion: NotionIcon,
  twitter: TwitterIcon,
  linkedin: LinkedInIcon,
  reddit: RedditIcon,
  lark: LarkIcon,
  whatsapp: WhatsAppIcon,
}

function GitHubIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
    </svg>
  )
}

function SlackIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A"/>
      <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#36C5F0"/>
      <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" fill="#2EB67D"/>
      <path d="M15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill="#ECB22E"/>
    </svg>
  )
}

function GmailIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z" fill="#EA4335"/>
    </svg>
  )
}

function GoogleCalendarIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path fill="#fff" d="M18.316 5.684H5.684v12.632h12.632z"/>
      <path fill="#1967D2" d="M15.789 17.053H8.21v-1.264h7.579zm0-2.526H8.21v-1.264h7.579zm0-2.527H8.21v-1.263h7.579z"/>
      <path fill="#1967D2" d="M18.316 24H5.684a1.684 1.684 0 0 1-1.684-1.684V5.684A1.684 1.684 0 0 1 5.684 4h12.632a1.684 1.684 0 0 1 1.684 1.684v16.632A1.684 1.684 0 0 1 18.316 24zM5.684 5.263a.421.421 0 0 0-.421.421v16.632c0 .232.189.421.421.421h12.632a.421.421 0 0 0 .421-.421V5.684a.421.421 0 0 0-.421-.421z"/>
      <path fill="#1967D2" d="M18.316 5.684H5.684V2.526h12.632z"/>
      <path fill="#EA4335" d="M8.211 0h1.263v2.526H8.211z"/>
      <path fill="#EA4335" d="M14.526 0h1.263v2.526h-1.263z"/>
    </svg>
  )
}

function GoogleDriveIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M8.009 15.534l-4.236 7.331H17.76l4.236-7.331H8.009z" fill="#4285F4"/>
      <path d="M15.991 15.534L8.009 1.135H0l7.982 14.399h8.009z" fill="#0F9D58"/>
      <path d="M15.991 15.534h8.009L16.018 1.135h-8.01l7.983 14.399z" fill="#FFCD40"/>
    </svg>
  )
}

function NotionIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.98-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466l1.823 1.447zm.793 3.08v13.906c0 .747.373 1.027 1.214.98l14.523-.84c.84-.047.934-.56.934-1.167V6.354c0-.606-.233-.933-.746-.886l-15.177.887c-.56.046-.748.326-.748.933zm14.337.746c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.746 0-.933-.234-1.495-.933l-4.577-7.186v6.953L12.1 19s0 .84-1.168.84l-3.222.187c-.093-.187 0-.653.327-.746l.84-.233V9.855L7.38 9.715c-.094-.42.14-1.026.793-1.073l3.456-.233 4.763 7.28v-6.44l-1.215-.14c-.093-.513.28-.886.746-.933l3.222-.186zM1.936 1.035L15.23.108c1.635-.14 2.055-.047 3.082.7l4.25 2.987c.7.513.933.653.933 1.213v16.378c0 1.026-.373 1.634-1.68 1.726l-15.458.934c-.98.047-1.448-.093-1.962-.747l-3.129-4.06c-.56-.747-.793-1.306-.793-1.96V2.667c0-.84.374-1.54 1.463-1.632z"/>
    </svg>
  )
}

function TwitterIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
    </svg>
  )
}

function LinkedInIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="#0A66C2">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
    </svg>
  )
}

function RedditIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="#FF4500">
      <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/>
    </svg>
  )
}

function LarkIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M12 2L2 7l10 5 10-5-10-5z" fill="#00D6B9"/>
      <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke="#00D6B9" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
    </svg>
  )
}

function WhatsAppIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="#25D366">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
    </svg>
  )
}
