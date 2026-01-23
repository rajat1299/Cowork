import { useState } from 'react'
import {
  Plus,
  Key,
  Star,
  MoreVertical,
  Eye,
  EyeOff,
  Loader2,
  Check,
  X,
  Trash2,
  AlertCircle,
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { useProviders, PROVIDER_TEMPLATES } from '../../hooks/useProviders'
import type { Provider } from '../../api/coreApi'

/**
 * Providers settings page - BYOK (Bring Your Own Key)
 * Manage API keys for OpenAI, Anthropic, Google, etc.
 */
export default function ProvidersSettings() {
  const {
    providers,
    isLoading,
    error,
    createProvider,
    updateProvider,
    deleteProvider,
    setPreferred,
    validateProvider,
    clearError,
  } = useProviders()

  const [editingProvider, setEditingProvider] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-medium text-ink">API Providers</h2>
          <p className="text-[13px] text-ink-subtle mt-1">
            Add your API keys to use your own models
          </p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-xl',
            'bg-burnt text-white text-[14px] font-medium',
            'hover:bg-burnt/90 transition-colors'
          )}
        >
          <Plus size={16} />
          Add Provider
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-between">
          <div className="flex items-center gap-2 text-red-400 text-[13px]">
            <AlertCircle size={16} />
            {error}
          </div>
          <button onClick={clearError} className="text-red-400 hover:text-red-300">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Loading state */}
      {isLoading && providers.length === 0 && (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={24} className="animate-spin text-ink-subtle" />
        </div>
      )}

      {/* Add provider form */}
      {showAddForm && (
        <AddProviderForm
          onClose={() => setShowAddForm(false)}
          onSubmit={async (data) => {
            const result = await createProvider(data)
            if (result) {
              setShowAddForm(false)
            }
          }}
          validateProvider={validateProvider}
          existingProviders={providers}
        />
      )}

      {/* Provider list */}
      {!isLoading && providers.length === 0 && !showAddForm ? (
        <div className="border border-dark-border border-dashed rounded-xl p-8 text-center">
          <div className="w-12 h-12 rounded-full bg-dark-surface flex items-center justify-center mx-auto mb-4">
            <Key size={24} className="text-ink-muted" />
          </div>
          <h3 className="text-[15px] font-medium text-ink mb-2">No providers configured</h3>
          <p className="text-[13px] text-ink-subtle mb-4">
            Add your API keys for OpenAI, Anthropic, or other providers to use your own models.
          </p>
          <button
            onClick={() => setShowAddForm(true)}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2 rounded-xl',
              'bg-dark-surface border border-dark-border',
              'text-ink text-[13px]',
              'hover:border-ink-faint transition-colors'
            )}
          >
            <Plus size={14} />
            Add your first provider
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {providers.map((provider) => (
            <ProviderCard
              key={provider.id}
              provider={provider}
              isEditing={editingProvider === String(provider.id)}
              onEdit={() => setEditingProvider(String(provider.id))}
              onCancelEdit={() => setEditingProvider(null)}
              onUpdate={async (data) => {
                const result = await updateProvider(provider.id, data)
                if (result) {
                  setEditingProvider(null)
                }
              }}
              onDelete={() => deleteProvider(provider.id)}
              onSetPreferred={() => setPreferred(provider.id)}
              validateProvider={validateProvider}
            />
          ))}
        </div>
      )}

      {/* Supported providers info */}
      <div className="mt-8 p-4 bg-dark-surface rounded-xl">
        <h4 className="text-[13px] font-medium text-ink mb-3">Supported Providers</h4>
        <div className="grid grid-cols-3 gap-3 text-[12px] text-ink-muted">
          {PROVIDER_TEMPLATES.map((template) => (
            <div key={template.id}>{template.name}</div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ============ Provider Card Component ============

interface ProviderCardProps {
  provider: Provider
  isEditing: boolean
  onEdit: () => void
  onCancelEdit: () => void
  onUpdate: (data: { api_key?: string; endpoint_url?: string; model_type?: string }) => Promise<void>
  onDelete: () => void
  onSetPreferred: () => void
  validateProvider: (data: { model_platform: string; model_type: string; api_key: string; url?: string }) => Promise<{ valid: boolean; message?: string }>
}

function ProviderCard({
  provider,
  isEditing,
  onEdit,
  onCancelEdit,
  onUpdate,
  onDelete,
  onSetPreferred,
  validateProvider,
}: ProviderCardProps) {
  const [showMenu, setShowMenu] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [endpoint, setEndpoint] = useState(provider.endpoint_url || '')
  const [modelType, setModelType] = useState(provider.model_type || '')
  const [showApiKey, setShowApiKey] = useState(false)
  const [isValidating, setIsValidating] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  const template = PROVIDER_TEMPLATES.find((t) => t.id === provider.provider_name)

  const handleSave = async () => {
    setIsValidating(true)
    setValidationError(null)

    // Validate first
    const result = await validateProvider({
      model_platform: provider.provider_name,
      model_type: modelType || provider.model_type || '',
      api_key: apiKey || 'existing',
      url: endpoint || provider.endpoint_url,
    })

    if (!result.valid) {
      setValidationError(result.message || 'Validation failed')
      setIsValidating(false)
      return
    }

    // Update provider
    await onUpdate({
      ...(apiKey && { api_key: apiKey }),
      ...(endpoint && { endpoint_url: endpoint }),
      ...(modelType && { model_type: modelType }),
    })

    setIsValidating(false)
    setApiKey('')
  }

  if (isEditing) {
    return (
      <div className="p-4 rounded-xl bg-dark-surface border border-burnt/30">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-dark-elevated flex items-center justify-center">
              <Key size={18} className="text-ink-muted" />
            </div>
            <div>
              <span className="text-[14px] font-medium text-ink">{template?.name || provider.provider_name}</span>
              <p className="text-[12px] text-ink-subtle">{template?.description}</p>
            </div>
          </div>
          <button onClick={onCancelEdit} className="p-2 text-ink-muted hover:text-ink">
            <X size={16} />
          </button>
        </div>

        <div className="space-y-3">
          {/* API Key */}
          <div>
            <label className="block text-[12px] text-ink-muted mb-1">API Key</label>
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={provider.api_key_last4 ? `****${provider.api_key_last4}` : 'Enter API key'}
                className={cn(
                  'w-full px-3 py-2 pr-10 rounded-lg',
                  'bg-dark-elevated border border-dark-border',
                  'text-ink text-[13px] placeholder:text-ink-subtle',
                  'focus:outline-none focus:border-burnt/50'
                )}
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink"
              >
                {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Endpoint URL */}
          <div>
            <label className="block text-[12px] text-ink-muted mb-1">Endpoint URL</label>
            <input
              type="text"
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              placeholder={template?.defaultEndpoint || 'https://api.example.com/v1'}
              className={cn(
                'w-full px-3 py-2 rounded-lg',
                'bg-dark-elevated border border-dark-border',
                'text-ink text-[13px] placeholder:text-ink-subtle',
                'focus:outline-none focus:border-burnt/50'
              )}
            />
          </div>

          {/* Model Type */}
          <div>
            <label className="block text-[12px] text-ink-muted mb-1">Model Type</label>
            <input
              type="text"
              value={modelType}
              onChange={(e) => setModelType(e.target.value)}
              placeholder={template?.supportedModels[0] || 'gpt-4o'}
              className={cn(
                'w-full px-3 py-2 rounded-lg',
                'bg-dark-elevated border border-dark-border',
                'text-ink text-[13px] placeholder:text-ink-subtle',
                'focus:outline-none focus:border-burnt/50'
              )}
            />
            {template && (
              <p className="text-[11px] text-ink-subtle mt-1">
                Supported: {template.supportedModels.slice(0, 3).join(', ')}
                {template.supportedModels.length > 3 && '...'}
              </p>
            )}
          </div>

          {/* Validation Error */}
          {validationError && (
            <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-[12px]">
              {validationError}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={onCancelEdit}
              className="px-3 py-1.5 rounded-lg text-[13px] text-ink-muted hover:text-ink"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isValidating}
              className={cn(
                'flex items-center gap-2 px-4 py-1.5 rounded-lg',
                'bg-burnt text-white text-[13px] font-medium',
                'hover:bg-burnt/90 disabled:opacity-50'
              )}
            >
              {isValidating ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Validating...
                </>
              ) : (
                'Save'
              )}
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className={cn(
        'flex items-center gap-4 p-4 rounded-xl',
        'bg-dark-surface border border-dark-border',
        provider.prefer && 'border-burnt/30'
      )}
    >
      <div className="w-10 h-10 rounded-lg bg-dark-elevated flex items-center justify-center">
        <Key size={18} className="text-ink-muted" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[14px] font-medium text-ink">{template?.name || provider.provider_name}</span>
          {provider.prefer && (
            <span className="flex items-center gap-1 text-[11px] text-burnt">
              <Star size={10} fill="currentColor" />
              Default
            </span>
          )}
          {provider.is_valid && (
            <span className="flex items-center gap-1 text-[11px] text-green-500">
              <Check size={10} />
              Verified
            </span>
          )}
        </div>
        <div className="text-[12px] text-ink-subtle">
          {provider.model_type || 'No model configured'}
          {provider.api_key_last4 && ` • ****${provider.api_key_last4}`}
        </div>
      </div>

      {/* Actions */}
      <div className="relative">
        <button
          onClick={() => setShowMenu(!showMenu)}
          className="p-2 rounded-lg hover:bg-dark-elevated transition-colors"
        >
          <MoreVertical size={16} className="text-ink-muted" />
        </button>

        {showMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
            <div className="absolute right-0 top-full mt-1 z-20 w-40 py-1 bg-dark-surface border border-dark-border rounded-lg shadow-lg">
              <button
                onClick={() => {
                  setShowMenu(false)
                  onEdit()
                }}
                className="w-full px-3 py-2 text-left text-[13px] text-ink hover:bg-dark-elevated"
              >
                Edit
              </button>
              {!provider.prefer && (
                <button
                  onClick={() => {
                    setShowMenu(false)
                    onSetPreferred()
                  }}
                  className="w-full px-3 py-2 text-left text-[13px] text-ink hover:bg-dark-elevated"
                >
                  Set as Default
                </button>
              )}
              <button
                onClick={() => {
                  setShowMenu(false)
                  onDelete()
                }}
                className="w-full px-3 py-2 text-left text-[13px] text-red-400 hover:bg-dark-elevated"
              >
                <span className="flex items-center gap-2">
                  <Trash2 size={14} />
                  Delete
                </span>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ============ Add Provider Form ============

interface AddProviderFormProps {
  onClose: () => void
  onSubmit: (data: { provider_name: string; api_key: string; endpoint_url?: string; model_type?: string }) => Promise<void>
  validateProvider: (data: { model_platform: string; model_type: string; api_key: string; url?: string }) => Promise<{ valid: boolean; message?: string }>
  existingProviders: Provider[]
}

function AddProviderForm({ onClose, onSubmit, validateProvider, existingProviders }: AddProviderFormProps) {
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [endpoint, setEndpoint] = useState('')
  const [modelType, setModelType] = useState('')
  const [showApiKey, setShowApiKey] = useState(false)
  const [isValidating, setIsValidating] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  const template = selectedTemplate ? PROVIDER_TEMPLATES.find((t) => t.id === selectedTemplate) : null
  const alreadyConfigured = existingProviders.map((p) => p.provider_name)

  const handleSubmit = async () => {
    if (!selectedTemplate || !apiKey) return

    setIsValidating(true)
    setValidationError(null)

    // Validate
    const result = await validateProvider({
      model_platform: selectedTemplate,
      model_type: modelType || template?.supportedModels[0] || '',
      api_key: apiKey,
      url: endpoint || template?.defaultEndpoint,
    })

    if (!result.valid) {
      setValidationError(result.message || 'Validation failed')
      setIsValidating(false)
      return
    }

    // Submit
    await onSubmit({
      provider_name: selectedTemplate,
      api_key: apiKey,
      endpoint_url: endpoint || template?.defaultEndpoint,
      model_type: modelType || template?.supportedModels[0],
    })

    setIsValidating(false)
  }

  return (
    <div className="mb-6 p-4 rounded-xl bg-dark-surface border border-dark-border">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-[14px] font-medium text-ink">Add Provider</h3>
        <button onClick={onClose} className="p-1 text-ink-muted hover:text-ink">
          <X size={16} />
        </button>
      </div>

      {!selectedTemplate ? (
        // Template selection
        <div className="grid grid-cols-2 gap-2">
          {PROVIDER_TEMPLATES.map((tmpl) => {
            const isConfigured = alreadyConfigured.includes(tmpl.id)
            return (
              <button
                key={tmpl.id}
                onClick={() => !isConfigured && setSelectedTemplate(tmpl.id)}
                disabled={isConfigured}
                className={cn(
                  'p-3 rounded-lg text-left',
                  'border border-dark-border',
                  'transition-colors',
                  isConfigured
                    ? 'opacity-50 cursor-not-allowed'
                    : 'hover:border-burnt/50 hover:bg-dark-elevated'
                )}
              >
                <div className="text-[13px] font-medium text-ink">{tmpl.name}</div>
                <div className="text-[11px] text-ink-subtle mt-1">
                  {isConfigured ? 'Already configured' : tmpl.description}
                </div>
              </button>
            )
          })}
        </div>
      ) : (
        // Configuration form
        <div className="space-y-3">
          <div className="flex items-center gap-2 mb-4">
            <button
              onClick={() => setSelectedTemplate(null)}
              className="text-ink-muted hover:text-ink text-[13px]"
            >
              ← Back
            </button>
            <span className="text-[14px] font-medium text-ink">{template?.name}</span>
          </div>

          {/* API Key */}
          {template?.requiresApiKey && (
            <div>
              <label className="block text-[12px] text-ink-muted mb-1">API Key *</label>
              <div className="relative">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Enter your API key"
                  className={cn(
                    'w-full px-3 py-2 pr-10 rounded-lg',
                    'bg-dark-elevated border border-dark-border',
                    'text-ink text-[13px] placeholder:text-ink-subtle',
                    'focus:outline-none focus:border-burnt/50'
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink"
                >
                  {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
          )}

          {/* Endpoint */}
          <div>
            <label className="block text-[12px] text-ink-muted mb-1">Endpoint URL</label>
            <input
              type="text"
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              placeholder={template?.defaultEndpoint}
              className={cn(
                'w-full px-3 py-2 rounded-lg',
                'bg-dark-elevated border border-dark-border',
                'text-ink text-[13px] placeholder:text-ink-subtle',
                'focus:outline-none focus:border-burnt/50'
              )}
            />
          </div>

          {/* Model Type */}
          <div>
            <label className="block text-[12px] text-ink-muted mb-1">Model Type</label>
            <input
              type="text"
              value={modelType}
              onChange={(e) => setModelType(e.target.value)}
              placeholder={template?.supportedModels[0]}
              className={cn(
                'w-full px-3 py-2 rounded-lg',
                'bg-dark-elevated border border-dark-border',
                'text-ink text-[13px] placeholder:text-ink-subtle',
                'focus:outline-none focus:border-burnt/50'
              )}
            />
            {template && (
              <p className="text-[11px] text-ink-subtle mt-1">
                Suggested: {template.supportedModels.join(', ')}
              </p>
            )}
          </div>

          {/* Validation Error */}
          {validationError && (
            <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-[12px]">
              {validationError}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 rounded-lg text-[13px] text-ink-muted hover:text-ink"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={isValidating || (template?.requiresApiKey && !apiKey)}
              className={cn(
                'flex items-center gap-2 px-4 py-1.5 rounded-lg',
                'bg-burnt text-white text-[13px] font-medium',
                'hover:bg-burnt/90 disabled:opacity-50'
              )}
            >
              {isValidating ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Validating...
                </>
              ) : (
                'Add Provider'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
