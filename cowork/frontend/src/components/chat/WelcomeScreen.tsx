import { FileText, BarChart3, Layers, FolderOpen, CalendarDays, MessageSquare } from 'lucide-react'
import { cn } from '../../lib/utils'

interface WelcomeScreenProps {
  onPromptSelect?: (prompt: string) => void
}

const actionCards = [
  { icon: FileText, label: 'Create a file', prompt: 'Help me create a file' },
  { icon: BarChart3, label: 'Crunch data', prompt: 'Help me analyze some data' },
  { icon: Layers, label: 'Make a prototype', prompt: 'Help me build a prototype' },
  { icon: FolderOpen, label: 'Organize files', prompt: 'Help me organize my files' },
  { icon: CalendarDays, label: 'Prep for a meeting', prompt: 'Help me prepare for a meeting' },
  { icon: MessageSquare, label: 'Draft a message', prompt: 'Help me draft a message' },
]

export function WelcomeScreen({ onPromptSelect }: WelcomeScreenProps) {
  return (
    <div className="h-full flex flex-col items-center justify-center px-6 pb-20">
      <div className="w-full max-w-[600px] animate-fade-in">
        {/* Burst Icon */}
        <div className="mb-4">
          <BurstIcon />
        </div>

        {/* Greeting */}
        <h1 className="text-[32px] font-medium text-ink tracking-tight mb-6">
          Let's knock something off your list
        </h1>

        {/* Research Preview Banner */}
        <div className="mb-8 p-4 bg-dark-surface rounded-xl border border-dark-border">
          <div className="flex items-start gap-3">
            <div className="w-5 h-5 flex items-center justify-center flex-shrink-0 mt-0.5">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-ink-muted">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M9 12h6M9 8h6M9 16h3" />
              </svg>
            </div>
            <p className="text-[14px] text-ink-muted leading-relaxed">
              Cowork is an early research preview. New improvements ship frequently.{' '}
              <a href="#" className="text-ink hover:text-burnt transition-colors">Learn more</a>
              {' '}or{' '}
              <a href="#" className="text-ink hover:text-burnt transition-colors">give us feedback</a>.
            </p>
          </div>
        </div>

        {/* Action Cards Grid */}
        <div className="grid grid-cols-3 gap-3">
          {actionCards.map((card, index) => (
            <ActionCard
              key={card.label}
              icon={card.icon}
              label={card.label}
              onClick={() => onPromptSelect?.(card.prompt)}
              delay={index * 50}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

interface ActionCardProps {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>
  label: string
  onClick?: () => void
  delay?: number
}

function ActionCard({ icon: Icon, label, onClick, delay = 0 }: ActionCardProps) {
  return (
    <button
      onClick={onClick}
      style={{ animationDelay: `${delay}ms` }}
      className={cn(
        'flex items-center gap-3 p-4 rounded-xl text-left',
        'bg-dark-surface border border-dark-border',
        'hover:bg-dark-elevated hover:border-ink-faint',
        'transition-all duration-200',
        'animate-slide-up opacity-0',
        'group'
      )}
    >
      <div className="w-9 h-9 rounded-lg bg-dark-elevated flex items-center justify-center group-hover:bg-burnt/10 transition-colors">
        <Icon size={18} strokeWidth={1.5} className="text-ink-muted group-hover:text-burnt transition-colors" />
      </div>
      <span className="text-[14px] text-ink-muted group-hover:text-ink transition-colors">
        {label}
      </span>
    </button>
  )
}

function BurstIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
      <g>
        {/* Main burst rays */}
        <line x1="24" y1="4" x2="24" y2="16" stroke="#FF4500" strokeWidth="3" strokeLinecap="round" />
        <line x1="24" y1="32" x2="24" y2="44" stroke="#FF4500" strokeWidth="3" strokeLinecap="round" />
        <line x1="4" y1="24" x2="16" y2="24" stroke="#FF4500" strokeWidth="3" strokeLinecap="round" />
        <line x1="32" y1="24" x2="44" y2="24" stroke="#FF4500" strokeWidth="3" strokeLinecap="round" />
        {/* Diagonal rays */}
        <line x1="9.9" y1="9.9" x2="17.5" y2="17.5" stroke="#FF4500" strokeWidth="3" strokeLinecap="round" />
        <line x1="30.5" y1="30.5" x2="38.1" y2="38.1" stroke="#FF4500" strokeWidth="3" strokeLinecap="round" />
        <line x1="38.1" y1="9.9" x2="30.5" y2="17.5" stroke="#FF4500" strokeWidth="3" strokeLinecap="round" />
        <line x1="17.5" y1="30.5" x2="9.9" y2="38.1" stroke="#FF4500" strokeWidth="3" strokeLinecap="round" />
        {/* Center dot */}
        <circle cx="24" cy="24" r="3" fill="#FF4500" />
      </g>
    </svg>
  )
}

