import { useState, useEffect } from 'react'
import {
  Box,
  Plus,
  Upload,
  AlertCircle,
  Check,
  Loader2,
  Trash2,
  Settings,
  Globe,
  Terminal,
  X,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  RefreshCw,
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { useMCP, validateMcpJson, DEFAULT_MCP_JSON } from '../../hooks/useMCP'
import type { McpUser, McpUserUpdate, McpImportLocal } from '../../api/coreApi'
import { showSuccess, showError } from '../../lib/toast'
import { MCPItemSkeleton } from '../../components/ui/skeletons'

type AddType = 'local' | 'remote'

/**
 * MCP (Model Context Protocol) settings page
 * Manages user's MCP server installations
 */
export default function MCPSettings() {
  const {
    userMcps,
    isLoading,
    error,
    fetchUserMcps,
    importLocal,
    importRemote,
    updateMcp,
    deleteMcp,
    toggleMcp,
    clearError,
  } = useMCP()

  // Dialog states
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [showConfigDialog, setShowConfigDialog] = useState<McpUser | null>(null)
  const [showDeleteDialog, setShowDeleteDialog] = useState<McpUser | null>(null)

  // Loading states for individual items
  const [togglingIds, setTogglingIds] = useState<Set<number>>(new Set())
  const [deletingId, setDeletingId] = useState<number | null>(null)

  // Section collapse state
  const [collapsed, setCollapsed] = useState(false)

  const handleToggle = async (id: number, enabled: boolean) => {
    setTogglingIds((s) => new Set(s).add(id))
    const success = await toggleMcp(id, enabled)
    if (success) {
      showSuccess(enabled ? 'MCP enabled' : 'MCP disabled')
    } else {
      showError('Failed to update MCP')
    }
    setTogglingIds((s) => {
      const next = new Set(s)
      next.delete(id)
      return next
    })
  }

  const handleDelete = async () => {
    if (!showDeleteDialog) return
    setDeletingId(showDeleteDialog.id)
    const success = await deleteMcp(showDeleteDialog.id)
    if (success) {
      showSuccess('MCP deleted')
      setShowDeleteDialog(null)
    } else {
      showError('Failed to delete MCP')
    }
    setDeletingId(null)
  }

  return (
    <div className="p-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-medium text-foreground">MCP Servers</h2>
          <p className="text-[13px] text-muted-foreground mt-1">
            Manage Model Context Protocol servers for extended capabilities
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchUserMcps()}
            disabled={isLoading}
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-xl',
              'bg-secondary border border-border',
              'text-muted-foreground text-[13px]',
              'hover:text-foreground hover:border-foreground/30 transition-colors',
              'disabled:opacity-50'
            )}
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setShowAddDialog(true)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-xl',
              'bg-burnt text-white text-[14px] font-medium',
              'hover:bg-burnt/90 transition-colors'
            )}
          >
            <Plus size={16} />
            Add MCP
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 flex items-start gap-3">
          <AlertCircle size={18} className="text-red-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-[13px] text-red-400">{error}</p>
          </div>
          <button onClick={clearError} className="text-red-400 hover:text-red-300">
            <X size={16} />
          </button>
        </div>
      )}

      {/* MCP List Section */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[13px] font-medium text-muted-foreground uppercase tracking-wide">
            Your MCP Servers ({userMcps.length})
          </h3>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1 text-muted-foreground hover:text-foreground transition-colors"
          >
            {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          </button>
        </div>

        {!collapsed && (
          <>
            {/* Loading state */}
            {isLoading && userMcps.length === 0 && (
              <div className="space-y-3">
                <MCPItemSkeleton />
                <MCPItemSkeleton />
                <MCPItemSkeleton />
              </div>
            )}

            {/* Empty state */}
            {!isLoading && userMcps.length === 0 && (
              <div className="border border-border border-dashed rounded-xl p-8 text-center">
                <div className="w-12 h-12 rounded-full bg-secondary flex items-center justify-center mx-auto mb-4">
                  <Box size={24} className="text-muted-foreground" />
                </div>
                <h4 className="text-[15px] font-medium text-foreground mb-2">No MCP servers installed</h4>
                <p className="text-[13px] text-muted-foreground mb-4">
                  Add MCP servers to extend your AI's capabilities with external tools.
                </p>
                <button
                  onClick={() => setShowAddDialog(true)}
                  className={cn(
                    'inline-flex items-center gap-2 px-4 py-2 rounded-xl',
                    'bg-burnt text-white text-[14px] font-medium',
                    'hover:bg-burnt/90 transition-colors'
                  )}
                >
                  <Plus size={16} />
                  Add your first MCP
                </button>
              </div>
            )}

            {/* MCP list */}
            {userMcps.length > 0 && (
              <div className="space-y-3">
                {userMcps.map((mcp) => (
                  <MCPCard
                    key={mcp.id}
                    mcp={mcp}
                    isToggling={togglingIds.has(mcp.id)}
                    onToggle={(enabled) => handleToggle(mcp.id, enabled)}
                    onConfigure={() => setShowConfigDialog(mcp)}
                    onDelete={() => setShowDeleteDialog(mcp)}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Help section */}
      <div className="p-4 bg-secondary rounded-xl">
        <h4 className="text-[13px] font-medium text-foreground mb-2">About MCP</h4>
        <p className="text-[12px] text-muted-foreground leading-relaxed mb-3">
          Model Context Protocol (MCP) servers extend AI capabilities by providing access to
          external tools, APIs, and data sources. You can add local MCP servers via JSON
          configuration or connect to remote servers via URL.
        </p>
        <a
          href="https://modelcontextprotocol.io/docs/getting-started/intro"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-[12px] text-burnt hover:underline"
        >
          Learn more about MCP
          <ExternalLink size={12} />
        </a>
      </div>

      {/* Add MCP Dialog */}
      <AddMCPDialog
        open={showAddDialog}
        onClose={() => setShowAddDialog(false)}
        onImportLocal={async (data) => {
          const success = await importLocal(data)
          if (success) setShowAddDialog(false)
          return success
        }}
        onImportRemote={async (data) => {
          const result = await importRemote(data)
          if (result) setShowAddDialog(false)
          return !!result
        }}
      />

      {/* Configure MCP Dialog */}
      <ConfigureMCPDialog
        mcp={showConfigDialog}
        onClose={() => setShowConfigDialog(null)}
        onSave={async (id, data) => {
          const result = await updateMcp(id, data)
          if (result) setShowConfigDialog(null)
          return !!result
        }}
      />

      {/* Delete MCP Dialog */}
      <DeleteMCPDialog
        mcp={showDeleteDialog}
        isDeleting={deletingId === showDeleteDialog?.id}
        onClose={() => setShowDeleteDialog(null)}
        onConfirm={handleDelete}
      />
    </div>
  )
}

// ============ MCP Card Component ============

interface MCPCardProps {
  mcp: McpUser
  isToggling: boolean
  onToggle: (enabled: boolean) => void
  onConfigure: () => void
  onDelete: () => void
}

function MCPCard({ mcp, isToggling, onToggle, onConfigure, onDelete }: MCPCardProps) {
  const isEnabled = mcp.status === 'enable'
  const isLocal = mcp.mcp_type === 'local'

  return (
    <div
      className={cn(
        'flex items-center gap-4 p-4 rounded-xl',
        'bg-secondary border border-border',
        'hover:border-foreground/30 transition-colors'
      )}
    >
      {/* Status indicator and icon */}
      <div className="relative">
        <div
          className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center',
            isEnabled ? 'bg-green-500/15' : 'bg-accent'
          )}
        >
          {isLocal ? (
            <Terminal size={18} className={isEnabled ? 'text-green-500' : 'text-muted-foreground'} />
          ) : (
            <Globe size={18} className={isEnabled ? 'text-green-500' : 'text-muted-foreground'} />
          )}
        </div>
        <div
          className={cn(
            'absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-secondary',
            isEnabled ? 'bg-green-500' : 'bg-muted-foreground'
          )}
        />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <h4 className="text-[14px] font-medium text-foreground truncate">{mcp.mcp_name}</h4>
          <span
            className={cn(
              'px-1.5 py-0.5 rounded text-[10px] font-medium uppercase',
              isLocal
                ? 'bg-blue-500/15 text-blue-400'
                : 'bg-purple-500/15 text-purple-400'
            )}
          >
            {mcp.mcp_type}
          </span>
        </div>
        {mcp.mcp_desc && (
          <p className="text-[12px] text-muted-foreground truncate">{mcp.mcp_desc}</p>
        )}
        {isLocal && mcp.command && (
          <p className="text-[11px] text-muted-foreground font-mono mt-1 truncate">
            {mcp.command} {mcp.args?.join(' ')}
          </p>
        )}
        {!isLocal && mcp.server_url && (
          <p className="text-[11px] text-muted-foreground truncate mt-1">{mcp.server_url}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {/* Toggle switch */}
        <button
          onClick={() => onToggle(!isEnabled)}
          disabled={isToggling}
          className={cn(
            'relative w-10 h-6 rounded-full transition-colors',
            isEnabled ? 'bg-green-500' : 'bg-accent',
            isToggling && 'opacity-50 cursor-not-allowed'
          )}
        >
          <div
            className={cn(
              'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
              isEnabled ? 'left-5' : 'left-1'
            )}
          />
        </button>

        {/* Configure button */}
        <button
          onClick={onConfigure}
          className={cn(
            'p-2 rounded-lg transition-colors',
            'text-muted-foreground hover:text-foreground hover:bg-accent'
          )}
        >
          <Settings size={16} />
        </button>

        {/* Delete button */}
        <button
          onClick={onDelete}
          className={cn(
            'p-2 rounded-lg transition-colors',
            'text-muted-foreground hover:text-red-400 hover:bg-red-500/10'
          )}
        >
          <Trash2 size={16} />
        </button>
      </div>
    </div>
  )
}

// ============ Add MCP Dialog ============

interface AddMCPDialogProps {
  open: boolean
  onClose: () => void
  onImportLocal: (data: McpImportLocal) => Promise<boolean>
  onImportRemote: (data: { server_name: string; server_url: string }) => Promise<boolean>
}

function AddMCPDialog({ open, onClose, onImportLocal, onImportRemote }: AddMCPDialogProps) {
  const [addType, setAddType] = useState<AddType>('local')
  const [localJson, setLocalJson] = useState(DEFAULT_MCP_JSON)
  const [remoteName, setRemoteName] = useState('')
  const [remoteUrl, setRemoteUrl] = useState('')
  const [installing, setInstalling] = useState(false)
  const [jsonError, setJsonError] = useState<string | null>(null)

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setLocalJson(DEFAULT_MCP_JSON)
      setRemoteName('')
      setRemoteUrl('')
      setJsonError(null)
    }
  }, [open])

  const handleInstall = async () => {
    setInstalling(true)
    setJsonError(null)

    try {
      if (addType === 'local') {
        const validation = validateMcpJson(localJson)
        if (!validation.valid) {
          setJsonError(validation.error || 'Invalid JSON')
          setInstalling(false)
          return
        }
        await onImportLocal(validation.data!)
      } else {
        if (!remoteName.trim()) {
          setJsonError('Server name is required')
          setInstalling(false)
          return
        }
        if (!remoteUrl.trim()) {
          setJsonError('Server URL is required')
          setInstalling(false)
          return
        }
        await onImportRemote({
          server_name: remoteName.trim(),
          server_url: remoteUrl.trim(),
        })
      }
    } finally {
      setInstalling(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Dialog */}
      <div className="relative w-full max-w-lg mx-4 bg-background border border-border rounded-2xl shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h3 className="text-[16px] font-medium text-foreground">Add MCP Server</h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary"
          >
            <X size={18} />
          </button>
        </div>

        {/* Type tabs */}
        <div className="px-6 pt-4">
          <div className="flex gap-1 p-1 bg-secondary rounded-xl">
            <button
              onClick={() => setAddType('local')}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-[13px] transition-colors',
                addType === 'local'
                  ? 'bg-accent text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <Terminal size={14} />
              Local
            </button>
            <button
              onClick={() => setAddType('remote')}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-[13px] transition-colors',
                addType === 'remote'
                  ? 'bg-accent text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <Globe size={14} />
              Remote
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          {jsonError && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <p className="text-[12px] text-red-400">{jsonError}</p>
            </div>
          )}

          {addType === 'local' ? (
            <div>
              <p className="text-[13px] text-muted-foreground mb-3">
                Add local MCP servers by providing a valid JSON configuration.{' '}
                <a
                  href="https://modelcontextprotocol.io/docs/getting-started/intro"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-burnt hover:underline"
                >
                  Learn more
                </a>
              </p>
              <textarea
                value={localJson}
                onChange={(e) => setLocalJson(e.target.value)}
                disabled={installing}
                className={cn(
                  'w-full h-64 p-3 rounded-xl font-mono text-[12px]',
                  'bg-secondary border border-border',
                  'text-foreground placeholder:text-muted-foreground',
                  'focus:outline-none focus:border-burnt/50',
                  'resize-none'
                )}
                spellCheck={false}
              />
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-[13px] text-muted-foreground">
                Connect to a remote MCP server by providing its name and URL.
              </p>
              <div>
                <label className="block text-[12px] text-muted-foreground mb-1.5">Server Name</label>
                <input
                  type="text"
                  value={remoteName}
                  onChange={(e) => setRemoteName(e.target.value)}
                  disabled={installing}
                  placeholder="my-remote-mcp"
                  className={cn(
                    'w-full px-3 py-2.5 rounded-xl',
                    'bg-secondary border border-border',
                    'text-foreground text-[14px] placeholder:text-muted-foreground',
                    'focus:outline-none focus:border-burnt/50'
                  )}
                />
              </div>
              <div>
                <label className="block text-[12px] text-muted-foreground mb-1.5">Server URL</label>
                <input
                  type="url"
                  value={remoteUrl}
                  onChange={(e) => setRemoteUrl(e.target.value)}
                  disabled={installing}
                  placeholder="https://mcp.example.com"
                  className={cn(
                    'w-full px-3 py-2.5 rounded-xl',
                    'bg-secondary border border-border',
                    'text-foreground text-[14px] placeholder:text-muted-foreground',
                    'focus:outline-none focus:border-burnt/50'
                  )}
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border">
          <button
            onClick={onClose}
            disabled={installing}
            className={cn(
              'px-4 py-2 rounded-xl text-[14px]',
              'text-muted-foreground hover:text-foreground transition-colors'
            )}
          >
            Cancel
          </button>
          <button
            onClick={handleInstall}
            disabled={installing}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-xl',
              'bg-burnt text-white text-[14px] font-medium',
              'hover:bg-burnt/90 transition-colors',
              'disabled:opacity-50'
            )}
          >
            {installing ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Installing...
              </>
            ) : (
              <>
                <Upload size={16} />
                Install
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// ============ Configure MCP Dialog ============

interface ConfigureMCPDialogProps {
  mcp: McpUser | null
  onClose: () => void
  onSave: (id: number, data: McpUserUpdate) => Promise<boolean>
}

function ConfigureMCPDialog({ mcp, onClose, onSave }: ConfigureMCPDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [command, setCommand] = useState('')
  const [args, setArgs] = useState('')
  const [serverUrl, setServerUrl] = useState('')
  const [env, setEnv] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  // Populate form when MCP changes
  useEffect(() => {
    if (mcp) {
      setName(mcp.mcp_name || '')
      setDescription(mcp.mcp_desc || '')
      setCommand(mcp.command || '')
      setArgs(mcp.args?.join(' ') || '')
      setServerUrl(mcp.server_url || '')
      setEnv(mcp.env || {})
    }
  }, [mcp])

  const handleSave = async () => {
    if (!mcp) return
    setSaving(true)

    const data: McpUserUpdate = {
      mcp_name: name,
      mcp_desc: description || undefined,
    }

    if (mcp.mcp_type === 'local') {
      data.command = command || undefined
      data.args = args.trim() ? args.split(/\s+/) : undefined
      data.env = Object.keys(env).length > 0 ? env : undefined
    } else {
      data.server_url = serverUrl || undefined
    }

    await onSave(mcp.id, data)
    setSaving(false)
  }

  const handleEnvChange = (key: string, value: string) => {
    setEnv((prev) => ({ ...prev, [key]: value }))
  }

  const handleEnvRemove = (key: string) => {
    setEnv((prev) => {
      const next = { ...prev }
      delete next[key]
      return next
    })
  }

  const handleEnvAdd = () => {
    const newKey = `NEW_VAR_${Object.keys(env).length + 1}`
    setEnv((prev) => ({ ...prev, [newKey]: '' }))
  }

  if (!mcp) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      <div className="relative w-full max-w-lg mx-4 bg-background border border-border rounded-2xl shadow-xl max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border flex-shrink-0">
          <h3 className="text-[16px] font-medium text-foreground">Configure MCP</h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 space-y-4 overflow-y-auto flex-1">
          {/* Name */}
          <div>
            <label className="block text-[12px] text-muted-foreground mb-1.5">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={saving}
              className={cn(
                'w-full px-3 py-2.5 rounded-xl',
                'bg-secondary border border-border',
                'text-foreground text-[14px]',
                'focus:outline-none focus:border-burnt/50'
              )}
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-[12px] text-muted-foreground mb-1.5">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={saving}
              placeholder="Optional description"
              className={cn(
                'w-full px-3 py-2.5 rounded-xl',
                'bg-secondary border border-border',
                'text-foreground text-[14px] placeholder:text-muted-foreground',
                'focus:outline-none focus:border-burnt/50'
              )}
            />
          </div>

          {/* Local-specific fields */}
          {mcp.mcp_type === 'local' && (
            <>
              <div>
                <label className="block text-[12px] text-muted-foreground mb-1.5">Command</label>
                <input
                  type="text"
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  disabled={saving}
                  placeholder="npx"
                  className={cn(
                    'w-full px-3 py-2.5 rounded-xl font-mono',
                    'bg-secondary border border-border',
                    'text-foreground text-[14px] placeholder:text-muted-foreground',
                    'focus:outline-none focus:border-burnt/50'
                  )}
                />
              </div>

              <div>
                <label className="block text-[12px] text-muted-foreground mb-1.5">Arguments</label>
                <input
                  type="text"
                  value={args}
                  onChange={(e) => setArgs(e.target.value)}
                  disabled={saving}
                  placeholder="-y @package/name"
                  className={cn(
                    'w-full px-3 py-2.5 rounded-xl font-mono',
                    'bg-secondary border border-border',
                    'text-foreground text-[14px] placeholder:text-muted-foreground',
                    'focus:outline-none focus:border-burnt/50'
                  )}
                />
              </div>

              {/* Environment variables */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-[12px] text-muted-foreground">Environment Variables</label>
                  <button
                    onClick={handleEnvAdd}
                    disabled={saving}
                    className="text-[11px] text-burnt hover:underline"
                  >
                    + Add variable
                  </button>
                </div>
                {Object.keys(env).length === 0 ? (
                  <p className="text-[12px] text-muted-foreground">No environment variables configured</p>
                ) : (
                  <div className="space-y-2">
                    {Object.entries(env).map(([key, value]) => (
                      <div key={key} className="flex items-center gap-2">
                        <input
                          type="text"
                          value={key}
                          onChange={(e) => {
                            const newKey = e.target.value
                            setEnv((prev) => {
                              const next = { ...prev }
                              delete next[key]
                              next[newKey] = value
                              return next
                            })
                          }}
                          disabled={saving}
                          className={cn(
                            'flex-1 px-2 py-1.5 rounded-lg font-mono text-[12px]',
                            'bg-secondary border border-border',
                            'text-foreground focus:outline-none focus:border-burnt/50'
                          )}
                        />
                        <span className="text-muted-foreground">=</span>
                        <input
                          type="text"
                          value={value}
                          onChange={(e) => handleEnvChange(key, e.target.value)}
                          disabled={saving}
                          className={cn(
                            'flex-1 px-2 py-1.5 rounded-lg font-mono text-[12px]',
                            'bg-secondary border border-border',
                            'text-foreground focus:outline-none focus:border-burnt/50'
                          )}
                        />
                        <button
                          onClick={() => handleEnvRemove(key)}
                          disabled={saving}
                          className="p-1 text-muted-foreground hover:text-red-400"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          {/* Remote-specific fields */}
          {mcp.mcp_type === 'remote' && (
            <div>
              <label className="block text-[12px] text-muted-foreground mb-1.5">Server URL</label>
              <input
                type="url"
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                disabled={saving}
                placeholder="https://mcp.example.com"
                className={cn(
                  'w-full px-3 py-2.5 rounded-xl',
                  'bg-secondary border border-border',
                  'text-foreground text-[14px] placeholder:text-muted-foreground',
                  'focus:outline-none focus:border-burnt/50'
                )}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border flex-shrink-0">
          <button
            onClick={onClose}
            disabled={saving}
            className={cn(
              'px-4 py-2 rounded-xl text-[14px]',
              'text-muted-foreground hover:text-foreground transition-colors'
            )}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-xl',
              'bg-burnt text-white text-[14px] font-medium',
              'hover:bg-burnt/90 transition-colors',
              'disabled:opacity-50'
            )}
          >
            {saving ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Check size={16} />
                Save Changes
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// ============ Delete MCP Dialog ============

interface DeleteMCPDialogProps {
  mcp: McpUser | null
  isDeleting: boolean
  onClose: () => void
  onConfirm: () => void
}

function DeleteMCPDialog({ mcp, isDeleting, onClose, onConfirm }: DeleteMCPDialogProps) {
  if (!mcp) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      <div className="relative w-full max-w-sm mx-4 bg-background border border-border rounded-2xl shadow-xl">
        <div className="p-6 text-center">
          <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-4">
            <Trash2 size={24} className="text-red-400" />
          </div>
          <h3 className="text-[16px] font-medium text-foreground mb-2">Delete MCP Server</h3>
          <p className="text-[13px] text-muted-foreground mb-6">
            Are you sure you want to delete <strong className="text-foreground">{mcp.mcp_name}</strong>?
            This action cannot be undone.
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={onClose}
              disabled={isDeleting}
              className={cn(
                'px-4 py-2 rounded-xl text-[14px]',
                'bg-secondary text-muted-foreground',
                'hover:text-foreground transition-colors'
              )}
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              disabled={isDeleting}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-xl',
                'bg-red-500 text-white text-[14px] font-medium',
                'hover:bg-red-600 transition-colors',
                'disabled:opacity-50'
              )}
            >
              {isDeleting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 size={16} />
                  Delete
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
