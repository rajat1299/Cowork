import { Box, Plus, Download, Upload, AlertCircle, Check, XCircle } from 'lucide-react'
import { cn } from '../../lib/utils'

/**
 * MCP (Model Context Protocol) settings page
 * TODO: Implement with GET /mcps, POST /mcp/install, POST /mcp/import
 */
export default function MCPSettings() {
  // TODO: Fetch MCP servers from /mcp/users
  const installedMCPs: any[] = []
  const availableMCPs: any[] = []

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-medium text-ink">MCP Servers</h2>
          <p className="text-[13px] text-ink-subtle mt-1">
            Manage Model Context Protocol servers
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-xl',
              'bg-dark-surface border border-dark-border',
              'text-ink-muted text-[13px]',
              'hover:text-ink hover:border-ink-faint transition-colors'
            )}
          >
            <Upload size={14} />
            Import
          </button>
          <button
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-xl',
              'bg-burnt text-white text-[14px] font-medium',
              'hover:bg-burnt/90 transition-colors'
            )}
          >
            <Plus size={16} />
            Install
          </button>
        </div>
      </div>

      {/* Installed MCP servers */}
      <div className="mb-8">
        <h3 className="text-[13px] font-medium text-ink-muted uppercase tracking-wide mb-3">
          Installed
        </h3>
        {installedMCPs.length === 0 ? (
          <div className="border border-dark-border border-dashed rounded-xl p-6 text-center">
            <div className="w-10 h-10 rounded-full bg-dark-surface flex items-center justify-center mx-auto mb-3">
              <Box size={20} className="text-ink-muted" />
            </div>
            <p className="text-[13px] text-ink-subtle">
              No MCP servers installed yet
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {installedMCPs.map((mcp) => (
              <MCPCard key={mcp.id} mcp={mcp} installed />
            ))}
          </div>
        )}
      </div>

      {/* Available MCP servers */}
      <div>
        <h3 className="text-[13px] font-medium text-ink-muted uppercase tracking-wide mb-3">
          Available
        </h3>
        {availableMCPs.length === 0 ? (
          <div className="p-4 bg-dark-surface rounded-xl">
            <p className="text-[13px] text-ink-subtle">
              Browse available MCP servers from the marketplace.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {availableMCPs.map((mcp) => (
              <MCPCard key={mcp.id} mcp={mcp} />
            ))}
          </div>
        )}
      </div>

      {/* Help section */}
      <div className="mt-8 p-4 bg-dark-surface rounded-xl">
        <h4 className="text-[13px] font-medium text-ink mb-2">About MCP</h4>
        <p className="text-[12px] text-ink-subtle leading-relaxed">
          Model Context Protocol (MCP) servers extend the capabilities of AI models
          by providing access to external tools and data sources. Import local MCP
          configurations or install from the marketplace.
        </p>
      </div>
    </div>
  )
}

interface MCPCardProps {
  mcp: {
    id: string
    name: string
    key: string
    type: 'local' | 'remote'
    status?: 'active' | 'inactive' | 'error'
    error_message?: string
  }
  installed?: boolean
}

function MCPCard({ mcp, installed }: MCPCardProps) {
  const statusIcon = {
    active: <Check size={14} className="text-green-500" />,
    inactive: <AlertCircle size={14} className="text-yellow-500" />,
    error: <XCircle size={14} className="text-red-500" />,
  }

  return (
    <div
      className={cn(
        'flex items-center gap-3 p-3 rounded-xl',
        'bg-dark-surface border border-dark-border',
        'hover:border-ink-faint transition-colors'
      )}
    >
      <div className="w-9 h-9 rounded-lg bg-dark-elevated flex items-center justify-center">
        <Box size={16} className="text-ink-muted" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-medium text-ink truncate">{mcp.name}</span>
          {installed && mcp.status && statusIcon[mcp.status]}
        </div>
        <div className="text-[11px] text-ink-subtle">
          {mcp.type === 'local' ? 'Local' : 'Remote'}
          {mcp.error_message && (
            <span className="text-red-400 ml-2">{mcp.error_message}</span>
          )}
        </div>
      </div>
      {!installed && (
        <button
          className={cn(
            'px-3 py-1.5 rounded-lg',
            'bg-dark-elevated text-ink-muted text-[12px]',
            'hover:text-ink transition-colors'
          )}
        >
          <Download size={14} />
        </button>
      )}
    </div>
  )
}
