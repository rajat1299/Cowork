import { Plus, Key, Star, MoreVertical } from 'lucide-react'
import { cn } from '../../lib/utils'

/**
 * Providers settings page - BYOK (Bring Your Own Key)
 * TODO: Implement with GET/POST/PUT/DELETE /providers
 */
export default function ProvidersSettings() {
  // TODO: Fetch providers from API
  const providers: any[] = []

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

      {/* Provider list */}
      {providers.length === 0 ? (
        <div className="border border-dark-border border-dashed rounded-xl p-8 text-center">
          <div className="w-12 h-12 rounded-full bg-dark-surface flex items-center justify-center mx-auto mb-4">
            <Key size={24} className="text-ink-muted" />
          </div>
          <h3 className="text-[15px] font-medium text-ink mb-2">No providers configured</h3>
          <p className="text-[13px] text-ink-subtle mb-4">
            Add your API keys for OpenAI, Anthropic, or other providers to use your own models.
          </p>
          <button
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
            <ProviderCard key={provider.id} provider={provider} />
          ))}
        </div>
      )}

      {/* Supported providers info */}
      <div className="mt-8 p-4 bg-dark-surface rounded-xl">
        <h4 className="text-[13px] font-medium text-ink mb-3">Supported Providers</h4>
        <div className="grid grid-cols-3 gap-3 text-[12px] text-ink-muted">
          <div>OpenAI</div>
          <div>Anthropic</div>
          <div>Google AI</div>
          <div>Azure OpenAI</div>
          <div>Cohere</div>
          <div>Mistral</div>
        </div>
      </div>
    </div>
  )
}

interface ProviderCardProps {
  provider: {
    id: string
    provider_name: string
    model_type: string
    api_key_last4?: string
    api_key_set?: boolean
    is_preferred?: boolean
  }
}

function ProviderCard({ provider }: ProviderCardProps) {
  return (
    <div
      className={cn(
        'flex items-center gap-4 p-4 rounded-xl',
        'bg-dark-surface border border-dark-border',
        provider.is_preferred && 'border-burnt/30'
      )}
    >
      <div className="w-10 h-10 rounded-lg bg-dark-elevated flex items-center justify-center">
        <Key size={18} className="text-ink-muted" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[14px] font-medium text-ink">{provider.provider_name}</span>
          {provider.is_preferred && (
            <span className="flex items-center gap-1 text-[11px] text-burnt">
              <Star size={10} fill="currentColor" />
              Preferred
            </span>
          )}
        </div>
        <div className="text-[12px] text-ink-subtle">
          {provider.model_type} {provider.api_key_last4 && `• ****${provider.api_key_last4}`}
        </div>
      </div>
      <button className="p-2 rounded-lg hover:bg-dark-elevated transition-colors">
        <MoreVertical size={16} className="text-ink-muted" />
      </button>
    </div>
  )
}
