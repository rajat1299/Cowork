import { useEffect, useMemo, useRef, useState, type ChangeEventHandler } from 'react'
import { config, skills, type Config, type Skill } from '../../api/coreApi'
import { cn } from '../../lib/utils'
import { useMemory, formatMemoryLastUpdated, MEMORY_CATEGORIES } from '../../hooks/useMemory'
import { ManageMemoryModal } from '../../components/memory/ManageMemoryModal'

const GOVERNED_MEMORY_CATEGORIES = [
  { id: 'work_context', label: 'Work context' },
  { id: 'personal_context', label: 'Personal context' },
  { id: 'tech_stack', label: 'Tech stack' },
  { id: 'preferences', label: 'Preferences' },
] as const
const DEFAULT_MEMORY_RETENTION_DAYS = 180
const DEFAULT_MEMORY_CATEGORY_IDS = GOVERNED_MEMORY_CATEGORIES.map((item) => item.id)
const DEFAULT_MEMORY_CATEGORY_SET = new Set<string>(DEFAULT_MEMORY_CATEGORY_IDS)

/**
 * Capabilities Settings Page
 * Contains Memory section with toggles and manage memory card
 */
export default function CapabilitiesSettings() {
  const [searchChatsEnabled, setSearchChatsEnabled] = useState(true)
  const [generateMemoryEnabled, setGenerateMemoryEnabled] = useState(true)
  const [memoryRetentionDays, setMemoryRetentionDays] = useState(DEFAULT_MEMORY_RETENTION_DAYS)
  const [enabledMemoryCategories, setEnabledMemoryCategories] = useState<string[]>(DEFAULT_MEMORY_CATEGORY_IDS)
  const [showMemoryModal, setShowMemoryModal] = useState(false)
  const [memoryConfigs, setMemoryConfigs] = useState<Record<string, Config>>({})
  const [skillItems, setSkillItems] = useState<Skill[]>([])
  const [skillsLoading, setSkillsLoading] = useState(true)
  const [skillsSaving, setSkillsSaving] = useState<string | null>(null)
  const [skillsQuery, setSkillsQuery] = useState('')
  const [skillsTab, setSkillsTab] = useState<'your' | 'example'>('your')
  const [skillsError, setSkillsError] = useState<string | null>(null)
  const [uploadingSkill, setUploadingSkill] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

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
        setMemoryRetentionDays(
          parseMemoryRetentionDays(
            mapped.MEMORY_RETENTION_DAYS?.value,
            DEFAULT_MEMORY_RETENTION_DAYS
          )
        )
        setEnabledMemoryCategories(
          parseMemoryCategoryConfig(
            mapped.MEMORY_ENABLED_CATEGORIES?.value,
            DEFAULT_MEMORY_CATEGORY_IDS
          )
        )
      } catch (error) {
        console.error('Failed to load memory settings:', error)
      }
    }
    loadConfigs()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    const loadSkills = async () => {
      setSkillsLoading(true)
      setSkillsError(null)
      try {
        const list = await skills.list()
        if (!active) return
        setSkillItems(list)
      } catch (error) {
        console.error('Failed to load skills:', error)
        if (active) {
          setSkillsError('Unable to load skills right now.')
        }
      } finally {
        if (active) {
          setSkillsLoading(false)
        }
      }
    }
    loadSkills()
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

  const handleRetentionDaysChange = async (days: number) => {
    setMemoryRetentionDays(days)
    const updated = await upsertMemoryConfig(
      memoryConfigs.MEMORY_RETENTION_DAYS,
      'MEMORY_RETENTION_DAYS',
      String(days)
    )
    if (updated) {
      setMemoryConfigs((prev) => ({ ...prev, [updated.key]: updated }))
    }
  }

  const handleCategoryToggle = async (categoryId: string, enabled: boolean) => {
    const next = enabled
      ? Array.from(new Set([...enabledMemoryCategories, categoryId]))
      : enabledMemoryCategories.filter((id) => id !== categoryId)
    const normalized = next.filter((id) => DEFAULT_MEMORY_CATEGORY_SET.has(id))
    if (normalized.length === 0) {
      return
    }
    setEnabledMemoryCategories(normalized)
    const serialized = serializeMemoryCategoryConfig(normalized)
    const updated = await upsertMemoryConfig(
      memoryConfigs.MEMORY_ENABLED_CATEGORIES,
      'MEMORY_ENABLED_CATEGORIES',
      serialized
    )
    if (updated) {
      setMemoryConfigs((prev) => ({ ...prev, [updated.key]: updated }))
    }
  }

  const filteredSkills = useMemo(() => {
    const query = skillsQuery.trim().toLowerCase()
    return skillItems.filter((item) => {
      if (skillsTab === 'example' && item.source !== 'example') return false
      if (skillsTab === 'your' && item.source === 'example') return false
      if (!query) return true
      const haystack = `${item.name} ${item.skill_id} ${item.description}`.toLowerCase()
      return haystack.includes(query)
    })
  }, [skillItems, skillsQuery, skillsTab])

  const handleSkillToggle = async (skillId: string, enabled: boolean) => {
    setSkillsSaving(skillId)
    setSkillsError(null)
    setSkillItems((prev) => prev.map((item) => (item.skill_id === skillId ? { ...item, enabled } : item)))
    try {
      const updated = await skills.toggle(skillId, enabled)
      setSkillItems((prev) => prev.map((item) => (item.skill_id === skillId ? updated : item)))
    } catch (error) {
      console.error('Failed to toggle skill:', error)
      setSkillsError('Unable to update skill toggle.')
      setSkillItems((prev) =>
        prev.map((item) => (item.skill_id === skillId ? { ...item, enabled: !enabled } : item))
      )
    } finally {
      setSkillsSaving((current) => (current === skillId ? null : current))
    }
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleUploadChange: ChangeEventHandler<HTMLInputElement> = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setUploadingSkill(true)
    setSkillsError(null)
    try {
      const created = await skills.upload(file, true)
      setSkillsTab('your')
      setSkillItems((prev) => {
        const withoutOld = prev.filter((item) => item.skill_id !== created.skill_id)
        return [created, ...withoutOld]
      })
      if (created.trust_state === 'review_required') {
        setSkillsError('Skill uploaded with warnings and left disabled by default. Review warnings before enabling.')
      } else if (created.trust_state === 'blocked') {
        setSkillsError('Skill upload is blocked by security policy.')
      }
    } catch (error) {
      console.error('Failed to upload skill:', error)
      setSkillsError('Unable to upload skill. Check that the zip includes skill.toml.')
    } finally {
      setUploadingSkill(false)
      event.currentTarget.value = ''
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

          <div className="flex items-center justify-between gap-4">
            <div className="flex-1">
              <p className="text-[14px] text-foreground">Memory retention window</p>
              <p className="text-[13px] text-muted-foreground">
                Auto-generated memory notes expire after this period unless pinned.
              </p>
            </div>
            <select
              value={memoryRetentionDays}
              onChange={(event) => handleRetentionDaysChange(Number(event.target.value))}
              className={cn(
                'px-3 py-2 rounded-lg min-w-[140px]',
                'bg-secondary border border-border',
                'text-foreground text-[13px]',
                'focus:outline-none focus:border-burnt/50'
              )}
            >
              <option value={30}>30 days</option>
              <option value={90}>90 days</option>
              <option value={180}>180 days</option>
              <option value={365}>365 days</option>
            </select>
          </div>

          <div>
            <p className="text-[14px] text-foreground mb-1">Auto-memory categories</p>
            <p className="text-[13px] text-muted-foreground mb-3">
              Select which categories Cowork can write to automatically.
            </p>
            <div className="grid grid-cols-2 gap-2">
              {GOVERNED_MEMORY_CATEGORIES.map((category) => {
                const enabled = enabledMemoryCategories.includes(category.id)
                return (
                  <label
                    key={category.id}
                    className={cn(
                      'flex items-center justify-between rounded-lg border px-3 py-2',
                      enabled
                        ? 'border-burnt/40 bg-burnt/10'
                        : 'border-border bg-secondary/40'
                    )}
                  >
                    <span className="text-[13px] text-foreground">{category.label}</span>
                    <input
                      type="checkbox"
                      checked={enabled}
                      onChange={(event) => handleCategoryToggle(category.id, event.target.checked)}
                      className="accent-burnt"
                    />
                  </label>
                )
              })}
            </div>
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

      {/* Skills Section */}
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
        <p className="text-[12px] text-muted-foreground mb-6">
          Disabled skills are unavailable to the model at runtime, even if they match your prompt.
        </p>

        {/* Search skills */}
        <div className="flex items-center gap-4 mb-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search"
              value={skillsQuery}
              onChange={(event) => setSkillsQuery(event.target.value)}
              className={cn(
                'w-full px-3 py-2 rounded-lg',
                'bg-secondary border border-border',
                'text-foreground text-[14px] placeholder:text-muted-foreground',
                'focus:outline-none focus:border-burnt/50'
              )}
            />
          </div>
          <button
            onClick={handleUploadClick}
            disabled={uploadingSkill}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg',
              'bg-secondary border border-border',
              'text-[13px] text-muted-foreground',
              'hover:text-foreground hover:border-foreground/30',
              'transition-colors',
              uploadingSkill && 'opacity-60 cursor-not-allowed'
            )}
          >
            <span>+</span>
            <span>{uploadingSkill ? 'Uploading...' : 'Add'}</span>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".zip,application/zip"
            onChange={handleUploadChange}
            className="hidden"
          />
        </div>

        {/* Skills tabs */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setSkillsTab('your')}
            className={cn(
              'px-4 py-2 rounded-lg text-[13px] font-medium',
              skillsTab === 'your'
                ? 'bg-secondary text-foreground'
                : 'text-muted-foreground hover:text-foreground transition-colors'
            )}
          >
            Your skills
          </button>
          <button
            onClick={() => setSkillsTab('example')}
            className={cn(
              'px-4 py-2 rounded-lg text-[13px] font-medium',
              skillsTab === 'example'
                ? 'bg-secondary text-foreground'
                : 'text-muted-foreground hover:text-foreground transition-colors'
            )}
          >
            Example skills
          </button>
        </div>

        {skillsError && (
          <div className="mb-4 rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-[13px] text-red-300">
            {skillsError}
          </div>
        )}

        {skillsLoading ? (
          <div className="text-center py-8">
            <p className="text-[14px] text-muted-foreground">Loading skills...</p>
          </div>
        ) : filteredSkills.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-[14px] text-muted-foreground">
              {skillsTab === 'example'
                ? 'No example skills found for this search.'
                : 'No skills added by you yet. Upload a skill zip to get started.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredSkills.map((skill) => (
              <div
                key={skill.skill_id}
                className={cn(
                  'rounded-xl border border-border bg-secondary/40 px-4 py-3',
                  'flex items-start gap-4'
                )}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-[14px] font-medium text-foreground">{skill.name}</p>
                    <span className="px-2 py-0.5 rounded-md bg-secondary text-[11px] text-muted-foreground font-medium">
                      {skill.source === 'example'
                        ? 'Example'
                        : skill.source === 'custom'
                        ? 'Custom'
                        : 'Built-in'}
                    </span>
                    {skill.trust_state === 'review_required' && (
                      <span className="px-2 py-0.5 rounded-md bg-amber-500/15 text-[11px] text-amber-300 font-medium">
                        Review required
                      </span>
                    )}
                    {skill.trust_state === 'blocked' && (
                      <span className="px-2 py-0.5 rounded-md bg-red-500/15 text-[11px] text-red-300 font-medium">
                        Blocked
                      </span>
                    )}
                  </div>
                  <p className="text-[13px] text-muted-foreground">{skill.description}</p>
                  {skill.security_warnings.length > 0 && (
                    <p className="mt-2 text-[12px] text-amber-300">
                      {skill.security_warnings[0]}
                    </p>
                  )}
                </div>
                <ToggleSwitch
                  enabled={skill.enabled}
                  disabled={skillsSaving === skill.skill_id || skill.trust_state === 'blocked'}
                  onChange={(enabled) => handleSkillToggle(skill.skill_id, enabled)}
                />
              </div>
            ))}
          </div>
        )}
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

function parseMemoryRetentionDays(value: string | undefined, defaultValue: number): number {
  if (!value) return defaultValue
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return defaultValue
  if (parsed < 1) return defaultValue
  return Math.round(parsed)
}

function parseMemoryCategoryConfig(value: string | undefined, defaultValue: string[]): string[] {
  if (!value) return [...defaultValue]
  const categories = value
    .split(',')
    .map((token) => token.trim().toLowerCase())
    .filter((token) => token.length > 0 && DEFAULT_MEMORY_CATEGORY_SET.has(token))
  if (categories.length === 0) {
    return [...defaultValue]
  }
  return Array.from(new Set(categories))
}

function serializeMemoryCategoryConfig(categories: string[]): string {
  const normalized = categories
    .map((token) => token.trim().toLowerCase())
    .filter((token) => DEFAULT_MEMORY_CATEGORY_SET.has(token))
  const deduped = Array.from(new Set(normalized))
  return deduped.join(',')
}

async function upsertMemoryConfig(
  existing: Config | undefined,
  key: string,
  value: boolean | string
): Promise<Config | null> {
  const payload = {
    group: 'memory',
    key,
    value: typeof value === 'boolean' ? (value ? 'true' : 'false') : value,
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
  disabled?: boolean
  onChange: (enabled: boolean) => void
}

function ToggleSwitch({ enabled, disabled = false, onChange }: ToggleSwitchProps) {
  return (
    <button
      disabled={disabled}
      onClick={() => onChange(!enabled)}
      className={cn(
        'relative w-11 h-6 rounded-full transition-colors flex-shrink-0',
        enabled ? 'bg-burnt' : 'bg-secondary border border-border',
        disabled && 'opacity-60 cursor-not-allowed'
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
