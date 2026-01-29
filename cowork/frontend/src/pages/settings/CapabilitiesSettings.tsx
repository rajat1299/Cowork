import { useEffect, useState } from 'react'
import { config, type Config } from '../../api/coreApi'
import { cn } from '../../lib/utils'
import { useMemory, formatMemoryLastUpdated, MEMORY_CATEGORIES } from '../../hooks/useMemory'
import { ManageMemoryModal } from '../../components/memory/ManageMemoryModal'

/**
 * Capabilities Settings Page
 * Contains Memory section with toggles and manage memory card
 */
export default function CapabilitiesSettings() {
  const [searchChatsEnabled, setSearchChatsEnabled] = useState(true)
  const [generateMemoryEnabled, setGenerateMemoryEnabled] = useState(true)
  const [showMemoryModal, setShowMemoryModal] = useState(false)
  const [memoryConfigs, setMemoryConfigs] = useState<Record<string, Config>>({})

  const { stats, notes, notesByCategory, isLoading, refresh } = useMemory()

  useEffect(() => {
    let active = true
    const loadConfigs = async () => {
      try {
        const entries = await config.list('memory')
        if (!active) return
        const mapped = entries.reduce<Record<string, Config>>((acc, entry) => {
          acc[entry.key] = entry
          return acc
        }, {})
        setMemoryConfigs(mapped)
        setSearchChatsEnabled(parseConfigFlag(mapped.MEMORY_SEARCH_PAST_CHATS?.value, true))
        setGenerateMemoryEnabled(parseConfigFlag(mapped.MEMORY_GENERATE_FROM_CHATS?.value, true))
      } catch (error) {
        console.error('Failed to load memory settings:', error)
      }
    }
    loadConfigs()
    return () => {
      active = false
    }
  }, [])

  const handleSearchToggle = async (enabled: boolean) => {
    setSearchChatsEnabled(enabled)
    const updated = await upsertMemoryConfig(
      memoryConfigs.MEMORY_SEARCH_PAST_CHATS,
      'MEMORY_SEARCH_PAST_CHATS',
      enabled
    )
    if (updated) {
      setMemoryConfigs((prev) => ({ ...prev, [updated.key]: updated }))
    }
  }

  const handleMemoryToggle = async (enabled: boolean) => {
    setGenerateMemoryEnabled(enabled)
    const updated = await upsertMemoryConfig(
      memoryConfigs.MEMORY_GENERATE_FROM_CHATS,
      'MEMORY_GENERATE_FROM_CHATS',
      enabled
    )
    if (updated) {
      setMemoryConfigs((prev) => ({ ...prev, [updated.key]: updated }))
    }
  }

  // Get preview text for the memory card (first category with content)
  const getMemoryPreview = () => {
    for (const category of MEMORY_CATEGORIES) {
      const categoryNotes = notesByCategory[category.id]
      if (categoryNotes && categoryNotes.length > 0) {
        const content = categoryNotes[0].content
        return content.length > 100 ? content.slice(0, 100) + '...' : content
      }
    }
    return 'No memory saved yet'
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h2 className="text-xl font-medium text-foreground mb-8">Capabilities</h2>

      {/* Memory Section */}
      <section className="mb-10">
        <h3 className="text-lg font-medium text-foreground mb-6">Memory</h3>

        <div className="space-y-6">
          {/* Search and reference chats toggle */}
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <p className="text-[14px] text-foreground">Search and reference chats</p>
              <p className="text-[13px] text-muted-foreground">
                Allow Cowork to search for relevant details in past chats.{' '}
                <a href="#" className="text-burnt hover:underline">
                  Learn more
                </a>
                .
              </p>
            </div>
            <ToggleSwitch
              enabled={searchChatsEnabled}
              onChange={handleSearchToggle}
            />
          </div>

          {/* Generate memory from chat history toggle */}
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <p className="text-[14px] text-foreground">Generate memory from chat history</p>
              <p className="text-[13px] text-muted-foreground">
                Allow Cowork to remember relevant context from your chats. This setting controls
                memory for both chats and projects.{' '}
                <a href="#" className="text-burnt hover:underline">
                  Learn more
                </a>
                .
              </p>
            </div>
            <ToggleSwitch
              enabled={generateMemoryEnabled}
              onChange={handleMemoryToggle}
            />
          </div>

          {/* Memory from your chats card */}
          <button
            onClick={() => setShowMemoryModal(true)}
            className={cn(
              'w-full flex items-start gap-4 p-4 rounded-xl',
              'bg-secondary border border-border',
              'hover:border-foreground/30 hover:bg-accent/50',
              'transition-all duration-200 text-left'
            )}
          >
            {/* Preview thumbnail */}
            <div
              className={cn(
                'w-24 h-16 rounded-lg flex-shrink-0',
                'bg-card border border-border',
                'p-2 overflow-hidden'
              )}
            >
              <p className="text-[8px] text-muted-foreground leading-tight line-clamp-4">
                {getMemoryPreview()}
              </p>
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <p className="text-[14px] font-medium text-foreground mb-1">
                Memory from your chats
              </p>
              <p className="text-[13px] text-muted-foreground">
                {isLoading
                  ? 'Loading...'
                  : stats?.last_updated_at
                  ? `${formatMemoryLastUpdated(stats.last_updated_at)} from your chats`
                  : 'No memory saved yet'}
              </p>
            </div>
          </button>
        </div>
      </section>

      {/* Skills Section (placeholder) */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <h3 className="text-lg font-medium text-foreground">Skills</h3>
          <span className="px-2 py-0.5 rounded-md bg-secondary text-[11px] text-muted-foreground font-medium">
            Preview
          </span>
        </div>

        <p className="text-[13px] text-muted-foreground mb-6">
          Repeatable, customizable instructions that Cowork can follow in any chat.{' '}
          <a href="#" className="text-burnt hover:underline">
            Learn more
          </a>
          .
        </p>

        {/* Search skills */}
        <div className="flex items-center gap-4 mb-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search"
              className={cn(
                'w-full px-3 py-2 rounded-lg',
                'bg-secondary border border-border',
                'text-foreground text-[14px] placeholder:text-muted-foreground',
                'focus:outline-none focus:border-burnt/50'
              )}
            />
          </div>
          <button
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg',
              'bg-secondary border border-border',
              'text-[13px] text-muted-foreground',
              'hover:text-foreground hover:border-foreground/30',
              'transition-colors'
            )}
          >
            <span>+</span>
            <span>Add</span>
          </button>
        </div>

        {/* Skills tabs */}
        <div className="flex gap-2 mb-6">
          <button
            className={cn(
              'px-4 py-2 rounded-lg text-[13px] font-medium',
              'bg-secondary text-foreground'
            )}
          >
            Your skills
          </button>
          <button
            className={cn(
              'px-4 py-2 rounded-lg text-[13px] font-medium',
              'text-muted-foreground hover:text-foreground',
              'transition-colors'
            )}
          >
            Example skills
          </button>
        </div>

        {/* Empty state */}
        <div className="text-center py-8">
          <p className="text-[14px] text-muted-foreground">No skills added by you yet</p>
        </div>
      </section>

      {/* Manage Memory Modal */}
      <ManageMemoryModal
        open={showMemoryModal}
        onClose={() => setShowMemoryModal(false)}
        notes={notes}
        notesByCategory={notesByCategory}
        onRefresh={refresh}
      />
    </div>
  )
}

const TRUTHY_VALUES = new Set(['1', 'true', 'yes', 'on'])

function parseConfigFlag(value?: string, defaultValue = true): boolean {
  if (value === undefined) return defaultValue
  return TRUTHY_VALUES.has(value.trim().toLowerCase())
}

async function upsertMemoryConfig(
  existing: Config | undefined,
  key: string,
  enabled: boolean
): Promise<Config | null> {
  const payload = {
    group: 'memory',
    key,
    value: enabled ? 'true' : 'false',
  }
  try {
    if (existing) {
      return await config.update(existing.id, payload)
    }
    return await config.create(payload)
  } catch (error) {
    console.error('Failed to save memory setting:', error)
    return null
  }
}

/**
 * Toggle switch component with onChange handler
 */
interface ToggleSwitchProps {
  enabled: boolean
  onChange: (enabled: boolean) => void
}

function ToggleSwitch({ enabled, onChange }: ToggleSwitchProps) {
  return (
    <button
      onClick={() => onChange(!enabled)}
      className={cn(
        'relative w-11 h-6 rounded-full transition-colors flex-shrink-0',
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
