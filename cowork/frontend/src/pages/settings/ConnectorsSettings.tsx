import { useState, useEffect } from 'react'
import {
  Plug,
  Check,
  AlertCircle,
  X,
  Eye,
  EyeOff,
  Loader2,
  MessageSquare,
  Trello,
  Search,
  Github,
  Calendar,
  HardDrive,
  Mail,
  Twitter,
  Linkedin,
  MessageCircle,
  FileSpreadsheet,
  Image,
  Code,
  Globe,
  Mic,
  FileText,
  Presentation,
  Bird,
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { useConnectors } from '../../hooks/useConnectors'
import type { ConfigGroup, Config } from '../../api/coreApi'

// Icon mapping for connector groups
const connectorIcons: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  slack: MessageSquare,
  notion: Trello,
  linear: Trello,
  search: Search,
  github: Github,
  'google-calendar': Calendar,
  'google-drive-mcp': HardDrive,
  'google-gmail': Mail,
  'x-twitter': Twitter,
  twitter: Twitter,
  linkedin: Linkedin,
  reddit: MessageCircle,
  whatsapp: MessageCircle,
  lark: Bird,
  excel: FileSpreadsheet,
  'dall-e': Image,
  'image-analysis': Image,
  'audio-analysis': Mic,
  'code-execution': Code,
  'craw4ai': Globe,
  'file-write': FileText,
  pptx: Presentation,
  'mcp-search': Search,
  'edgeone-pages-mcp': Globe,
}

/**
 * Connectors settings page
 * Fetches groups from /config/info and manages configs via /configs
 */
export default function ConnectorsSettings() {
  const {
    groups,
    configs,
    isLoading,
    error,
    fetchConfigsForGroup,
    saveConnectorConfig,
    isGroupConfigured,
    getConfiguredCount,
  } = useConnectors()

  const [selectedGroup, setSelectedGroup] = useState<ConfigGroup | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // Fetch configs for all groups on mount
  useEffect(() => {
    groups.forEach((group) => {
      fetchConfigsForGroup(group.id)
    })
  }, [groups, fetchConfigsForGroup])

  const handleOpenConfig = (group: ConfigGroup) => {
    setSelectedGroup(group)
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setSelectedGroup(null)
  }

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center h-full">
        <div className="text-center">
          <Loader2 size={32} className="text-burnt animate-spin mx-auto mb-3" />
          <p className="text-[14px] text-ink-subtle">Loading connectors...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-center">
          <AlertCircle size={24} className="text-red-400 mx-auto mb-2" />
          <p className="text-[14px] text-red-400">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl">
      <div className="mb-6">
        <h2 className="text-lg font-medium text-ink">Connectors</h2>
        <p className="text-[13px] text-ink-subtle mt-1">
          Configure integrations with external services. Click a connector to set up its credentials.
        </p>
      </div>

      {/* Connector grid */}
      {groups.length === 0 ? (
        <div className="border border-dark-border border-dashed rounded-xl p-8 text-center">
          <div className="w-12 h-12 rounded-full bg-dark-surface flex items-center justify-center mx-auto mb-4">
            <Plug size={24} className="text-ink-muted" />
          </div>
          <h3 className="text-[15px] font-medium text-ink mb-2">No connectors available</h3>
          <p className="text-[13px] text-ink-subtle">
            Check backend configuration for available integrations.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {groups.map((group) => (
            <ConnectorCard
              key={group.id}
              group={group}
              isConfigured={isGroupConfigured(group.id)}
              configuredCount={getConfiguredCount(group.id)}
              onClick={() => handleOpenConfig(group)}
            />
          ))}
        </div>
      )}

      {/* Config summary */}
      <div className="mt-8 p-4 bg-dark-surface rounded-xl border border-dark-border">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-[14px] font-medium text-ink">
              {groups.length} connectors available
            </h4>
            <p className="text-[12px] text-ink-subtle mt-0.5">
              {groups.filter((g) => isGroupConfigured(g.id)).length} configured
            </p>
          </div>
          <div className="text-[12px] text-ink-subtle">
            Click a connector to configure its settings
          </div>
        </div>
      </div>

      {/* Configuration Modal */}
      {isModalOpen && selectedGroup && (
        <ConnectorConfigModal
          group={selectedGroup}
          existingConfigs={configs[selectedGroup.id] || []}
          onSave={saveConnectorConfig}
          onClose={handleCloseModal}
        />
      )}
    </div>
  )
}

interface ConnectorCardProps {
  group: ConfigGroup
  isConfigured: boolean
  configuredCount: number
  onClick: () => void
}

function ConnectorCard({ group, isConfigured, configuredCount, onClick }: ConnectorCardProps) {
  const Icon = connectorIcons[group.id.toLowerCase()] || connectorIcons[group.icon || ''] || Plug

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full p-4 rounded-xl text-left',
        'bg-dark-surface border border-dark-border',
        'hover:border-ink-faint hover:bg-dark-elevated',
        'transition-all duration-200',
        'group'
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center',
            'transition-colors',
            isConfigured ? 'bg-burnt/15' : 'bg-dark-elevated group-hover:bg-dark-surface'
          )}
        >
          <Icon
            size={20}
            className={cn(
              'transition-colors',
              isConfigured ? 'text-burnt' : 'text-ink-muted group-hover:text-ink'
            )}
          />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="text-[14px] font-medium text-ink">{group.name}</span>
            {isConfigured ? (
              <div className="flex items-center gap-1 text-green-500">
                <Check size={14} />
                <span className="text-[11px]">Configured</span>
              </div>
            ) : (
              <AlertCircle size={14} className="text-ink-subtle" />
            )}
          </div>
          <div className="text-[12px] text-ink-subtle mt-1">
            {configuredCount}/{group.fields?.length || 0} fields set
          </div>
        </div>
      </div>
    </button>
  )
}

interface ConnectorConfigModalProps {
  group: ConfigGroup
  existingConfigs: Config[]
  onSave: (groupId: string, fields: Record<string, string>) => Promise<void>
  onClose: () => void
}

function ConnectorConfigModal({
  group,
  existingConfigs,
  onSave,
  onClose,
}: ConnectorConfigModalProps) {
  const [fields, setFields] = useState<Record<string, string>>(() => {
    // Initialize with existing config values
    const initial: Record<string, string> = {}
    group.fields?.forEach((field) => {
      const existing = existingConfigs.find((c) => c.key === field.key)
      initial[field.key] = existing?.value || ''
    })
    return initial
  })
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const handleFieldChange = (key: string, value: string) => {
    setFields((prev) => ({ ...prev, [key]: value }))
  }

  const toggleShowSecret = (key: string) => {
    setShowSecrets((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    setSaveError(null)
    try {
      await onSave(group.id, fields)
      onClose()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save configuration')
    } finally {
      setIsSaving(false)
    }
  }

  const isSecretField = (key: string) => {
    const lowerKey = key.toLowerCase()
    return (
      lowerKey.includes('secret') ||
      lowerKey.includes('token') ||
      lowerKey.includes('key') ||
      lowerKey.includes('password')
    )
  }

  const Icon = connectorIcons[group.id.toLowerCase()] || Plug

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-lg mx-4 bg-dark-bg border border-dark-border rounded-2xl shadow-2xl animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-dark-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-burnt/15 flex items-center justify-center">
              <Icon size={20} className="text-burnt" />
            </div>
            <div>
              <h3 className="text-[16px] font-medium text-ink">{group.name}</h3>
              <p className="text-[12px] text-ink-subtle">Configure connector settings</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-ink-subtle hover:text-ink hover:bg-dark-surface transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 max-h-[60vh] overflow-y-auto">
          {group.fields?.map((field) => {
            const isSecret = isSecretField(field.key)
            const showValue = !isSecret || showSecrets[field.key]

            return (
              <div key={field.key}>
                <label className="block text-[13px] font-medium text-ink mb-1.5">
                  {field.label || field.key}
                  {field.required && <span className="text-burnt ml-1">*</span>}
                </label>
                <div className="relative">
                  <input
                    type={showValue ? 'text' : 'password'}
                    value={fields[field.key] || ''}
                    onChange={(e) => handleFieldChange(field.key, e.target.value)}
                    placeholder={`Enter ${field.label || field.key}`}
                    className={cn(
                      'w-full px-4 py-2.5 rounded-xl',
                      'bg-dark-surface border border-dark-border',
                      'text-[14px] text-ink placeholder:text-ink-subtle',
                      'focus:outline-none focus:border-burnt/50',
                      'transition-colors',
                      isSecret && 'pr-10'
                    )}
                  />
                  {isSecret && (
                    <button
                      type="button"
                      onClick={() => toggleShowSecret(field.key)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-subtle hover:text-ink transition-colors"
                    >
                      {showValue ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  )}
                </div>
                {field.type && (
                  <p className="text-[11px] text-ink-subtle mt-1">Type: {field.type}</p>
                )}
              </div>
            )
          })}

          {(!group.fields || group.fields.length === 0) && (
            <div className="text-center py-4">
              <p className="text-[13px] text-ink-subtle">
                No configuration fields for this connector.
              </p>
            </div>
          )}

          {saveError && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <p className="text-[13px] text-red-400">{saveError}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-5 border-t border-dark-border">
          <button
            onClick={onClose}
            className={cn(
              'px-4 py-2 rounded-xl',
              'text-[13px] text-ink-muted',
              'hover:text-ink hover:bg-dark-surface',
              'transition-colors'
            )}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-xl',
              'bg-burnt text-white',
              'text-[13px] font-medium',
              'hover:bg-burnt/90',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'transition-colors'
            )}
          >
            {isSaving && <Loader2 size={14} className="animate-spin" />}
            {isSaving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </div>
    </div>
  )
}
