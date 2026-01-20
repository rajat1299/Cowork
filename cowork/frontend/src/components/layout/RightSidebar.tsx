import { Plus, ChevronRight, X } from 'lucide-react'
import { cn } from '../../lib/utils'

interface RightSidebarProps {
  className?: string
}

export function RightSidebar({ className }: RightSidebarProps) {
  return (
    <aside className={cn(
      'w-72 h-full flex flex-col',
      'border-l border-dark-border',
      'bg-dark-bg',
      className
    )}>
      {/* Main sections */}
      <div className="flex-1 overflow-y-auto scrollbar-hide p-4 space-y-6">
        {/* Progress Section */}
        <Section title="Progress">
          <div className="flex items-center gap-2">
            {/* Progress circles */}
            <ProgressCircle status="completed" />
            <div className="w-4 h-px bg-dark-border" />
            <ProgressCircle status="completed" />
            <div className="w-4 h-px bg-dark-border" />
            <ProgressCircle status="active" />
            <div className="w-4 h-px bg-dark-border" />
            <ProgressCircle status="pending" />
          </div>
          <p className="text-[13px] text-ink-subtle mt-3">
            Steps will show as the task unfolds.
          </p>
        </Section>

        {/* Artifacts Section */}
        <Section title="Artifacts">
          <div className="grid grid-cols-3 gap-2">
            <ArtifactPlaceholder />
          </div>
          <p className="text-[13px] text-ink-subtle mt-3">
            Outputs created during the task land here.
          </p>
        </Section>

        {/* Context Section */}
        <Section title="Context">
          <div className="flex items-center gap-2">
            <ContextCard />
            <ContextCard active />
          </div>
          <p className="text-[13px] text-ink-subtle mt-3">
            Track the tools and files in use as Claude works.
          </p>
        </Section>
      </div>

      {/* Suggested Connectors */}
      <div className="border-t border-dark-border p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[14px] font-medium text-ink">Suggested connectors</h3>
          <button className="p-1 rounded hover:bg-dark-surface transition-colors">
            <X size={14} className="text-ink-subtle" />
          </button>
        </div>
        <p className="text-[12px] text-ink-subtle mb-4">
          Cowork uses connectors to browse websites, manage tasks, and more.
        </p>
        
        <div className="space-y-2">
          <ConnectorItem icon="chrome" label="Claude in Chrome" />
          <ConnectorItem icon="notion" label="Notion" />
          <ConnectorItem icon="linear" label="Linear" />
        </div>

        <button className="flex items-center gap-1 mt-4 text-[13px] text-ink-muted hover:text-ink transition-colors">
          <span>See all connectors</span>
          <ChevronRight size={14} />
        </button>
      </div>
    </aside>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-[14px] font-medium text-ink mb-3">{title}</h3>
      {children}
    </div>
  )
}

function ProgressCircle({ status }: { status: 'completed' | 'active' | 'pending' }) {
  return (
    <div className={cn(
      'w-6 h-6 rounded-full flex items-center justify-center',
      status === 'completed' && 'bg-warm-beige/20',
      status === 'active' && 'bg-burnt/20 ring-2 ring-burnt/30',
      status === 'pending' && 'bg-dark-surface border border-dark-border'
    )}>
      {status === 'completed' && (
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2.5 6L5 8.5L9.5 4" stroke="#F5E8D8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
      {status === 'active' && (
        <div className="w-2 h-2 rounded-full bg-burnt" />
      )}
    </div>
  )
}

function ArtifactPlaceholder() {
  return (
    <div className="aspect-[4/3] rounded-lg bg-dark-surface border border-dark-border flex items-center justify-center">
      <div className="space-y-1">
        <div className="w-6 h-1 bg-ink-faint rounded" />
        <div className="w-8 h-1 bg-ink-faint rounded" />
        <div className="w-5 h-1 bg-ink-faint rounded" />
      </div>
    </div>
  )
}

function ContextCard({ active = false }: { active?: boolean }) {
  return (
    <div className={cn(
      'w-12 h-10 rounded-lg flex items-center justify-center',
      'border transition-all duration-200',
      active 
        ? 'bg-dark-elevated border-burnt/30' 
        : 'bg-dark-surface border-dark-border'
    )}>
      <div className="space-y-0.5">
        <div className="w-5 h-0.5 bg-ink-faint rounded" />
        <div className="w-6 h-0.5 bg-ink-faint rounded" />
        <div className="w-4 h-0.5 bg-ink-faint rounded" />
      </div>
    </div>
  )
}

function ConnectorItem({ icon, label }: { icon: string; label: string }) {
  return (
    <div className={cn(
      'flex items-center justify-between p-3 rounded-xl',
      'bg-dark-surface border border-dark-border',
      'hover:border-ink-faint transition-all duration-200',
      'group cursor-pointer'
    )}>
      <div className="flex items-center gap-3">
        <ConnectorIcon type={icon} />
        <span className="text-[13px] text-ink-muted group-hover:text-ink transition-colors">
          {label}
        </span>
      </div>
      <button className={cn(
        'w-6 h-6 rounded-md flex items-center justify-center',
        'bg-dark-elevated text-ink-subtle',
        'hover:bg-burnt hover:text-white',
        'transition-all duration-200'
      )}>
        <Plus size={14} strokeWidth={2} />
      </button>
    </div>
  )
}

function ConnectorIcon({ type }: { type: string }) {
  const baseClass = "w-6 h-6 rounded flex items-center justify-center"
  
  switch (type) {
    case 'chrome':
      return (
        <div className={cn(baseClass, 'bg-gradient-to-br from-red-500 via-yellow-400 to-green-500')}>
          <div className="w-2.5 h-2.5 rounded-full bg-white" />
        </div>
      )
    case 'notion':
      return (
        <div className={cn(baseClass, 'bg-white')}>
          <span className="text-[10px] font-bold text-black">N</span>
        </div>
      )
    case 'linear':
      return (
        <div className={cn(baseClass, 'bg-[#5E6AD2]')}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="white">
            <path d="M0.5 9.5L9.5 0.5L11.5 2.5L2.5 11.5L0.5 9.5Z" />
          </svg>
        </div>
      )
    default:
      return <div className={cn(baseClass, 'bg-dark-elevated')} />
  }
}

