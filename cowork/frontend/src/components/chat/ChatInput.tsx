import { useState, useRef, useEffect, useCallback } from 'react'
import { FolderOpen, Plus, ChevronDown, ArrowRight, X, FileText } from 'lucide-react'
import { cn } from '../../lib/utils'
import { ChatInputMenu } from './ChatInputMenu'
import type { ChatMessageOptions } from '../../hooks/useChat'
import { generateId } from '../../types/chat'

interface ChatInputProps {
  onSend: (message: string, options?: ChatMessageOptions) => void
  disabled?: boolean
  isWelcome?: boolean
}

// Map connector IDs to their tool names for the agents config
const CONNECTOR_TOOL_MAP: Record<string, string> = {
  github: 'github',
  slack: 'slack',
  notion: 'notion',
  notion_mcp: 'notion_mcp',
  google_calendar: 'google_calendar',
  google_drive_mcp: 'google_drive_mcp',
  google_gmail_mcp: 'gmail',
  twitter: 'twitter',
  linkedin: 'linkedin',
  reddit: 'reddit',
  lark: 'lark',
  whatsapp: 'whatsapp',
}

export function ChatInput({ onSend, disabled = false, isWelcome = false }: ChatInputProps) {
  const [value, setValue] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [searchEnabled, setSearchEnabled] = useState(true)
  const [activeConnectors, setActiveConnectors] = useState<Array<{ id: string; name: string }>>([])
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([])
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`
    }
  }, [value])

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim()
    if (disabled || (!trimmed && pendingFiles.length === 0)) {
      return
    }
    const messageText = trimmed || 'Please review the attached files.'
    // Build agents config if connectors are active
    const options: ChatMessageOptions = {
      searchEnabled,
      files: pendingFiles.map((item) => item.file),
    }
    if (activeConnectors.length > 0) {
      const tools = activeConnectors.map((c) => CONNECTOR_TOOL_MAP[c.id] || c.id)
      options.agents = [
        { name: 'developer_agent', tools: ['terminal', 'file_write', 'code_execution', ...tools] }
      ]
    }
    onSend(messageText, options)
    setValue('')
    pendingFiles.forEach((item) => {
      if (item.previewUrl) {
        URL.revokeObjectURL(item.previewUrl)
      }
    })
    setPendingFiles([])
    // Clear connectors after sending (they were for this message)
    setActiveConnectors([])
  }, [value, disabled, onSend, searchEnabled, activeConnectors, pendingFiles])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleScreenshot = useCallback(() => {
    // Send screenshot request with screenshot tool enabled
    onSend('Take a screenshot of the current screen', {
      searchEnabled,
      agents: [
        { name: 'developer_agent', tools: ['terminal', 'file_write', 'code_execution', 'screenshot'] }
      ],
    })
  }, [onSend, searchEnabled])

  const handleAddFiles = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const handleFilesSelected = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || [])
    if (files.length === 0) return

    setPendingFiles((prev) => [
      ...prev,
      ...files.map((file) => ({
        id: generateId(),
        file,
        previewUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
        kind: (file.type.startsWith('image/') ? 'image' : 'file') as 'image' | 'file',
      })),
    ])

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [])

  const handleRemoveFile = useCallback((id: string) => {
    setPendingFiles((prev) => {
      const target = prev.find((item) => item.id === id)
      if (target?.previewUrl) {
        URL.revokeObjectURL(target.previewUrl)
      }
      return prev.filter((item) => item.id !== id)
    })
  }, [])

  const handleSearchToggle = useCallback(() => {
    setSearchEnabled((prev) => !prev)
  }, [])

  const handleAddConnector = useCallback((connectorId: string, connectorName: string) => {
    setActiveConnectors((prev) => {
      // Don't add duplicates
      if (prev.some((c) => c.id === connectorId)) return prev
      return [...prev, { id: connectorId, name: connectorName }]
    })
  }, [])

  const handleRemoveConnector = useCallback((connectorId: string) => {
    setActiveConnectors((prev) => prev.filter((c) => c.id !== connectorId))
  }, [])

  if (isWelcome) {
    return (
      <div className="space-y-3">
        {pendingFiles.length > 0 && (
          <AttachmentPreviewList items={pendingFiles} onRemove={handleRemoveFile} />
        )}
        {/* Main input */}
        <div className="relative bg-secondary rounded-2xl border border-border overflow-hidden">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="How can I help you today?"
            disabled={disabled}
            rows={1}
            className={cn(
              'w-full resize-none bg-transparent px-5 py-4',
              'text-[15px] text-foreground leading-relaxed',
              'placeholder:text-muted-foreground',
              'focus:outline-none',
              'disabled:opacity-50'
            )}
          />
        </div>

        {/* Bottom row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {/* Work in a folder button */}
            <button className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-lg',
              'text-[13px] text-muted-foreground',
              'hover:bg-secondary hover:text-foreground',
              'transition-all duration-200',
              'border border-transparent hover:border-border'
            )}>
              <FolderOpen size={16} strokeWidth={1.5} />
              <span>Work in a folder</span>
            </button>

            {/* Add attachment - with menu */}
            <div className="relative">
              <button
                ref={menuButtonRef}
                onClick={() => setMenuOpen((prev) => !prev)}
                aria-label="Add attachment"
                aria-expanded={menuOpen}
                className={cn(
                  'w-8 h-8 rounded-lg flex items-center justify-center',
                  'text-muted-foreground hover:text-foreground hover:bg-secondary',
                  'transition-all duration-200',
                  menuOpen && 'bg-secondary text-foreground'
                )}
              >
                <Plus size={18} strokeWidth={1.5} />
              </button>

              <ChatInputMenu
                isOpen={menuOpen}
                onClose={() => setMenuOpen(false)}
                searchEnabled={searchEnabled}
                onSearchToggle={handleSearchToggle}
                onScreenshot={handleScreenshot}
                onAddFiles={handleAddFiles}
                onAddConnector={handleAddConnector}
              />
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFilesSelected}
            />

            {/* Active connectors chips */}
            {activeConnectors.map((connector) => (
              <ConnectorChip
                key={connector.id}
                name={connector.name}
                onRemove={() => handleRemoveConnector(connector.id)}
              />
            ))}
          </div>

          <div className="flex items-center gap-3">
            {/* Model selector */}
            <button className={cn(
              'flex items-center gap-1.5 px-3 py-2 rounded-lg',
              'text-[13px] text-muted-foreground',
              'hover:bg-secondary',
              'transition-all duration-200'
            )}>
              <span>Opus 4.5</span>
              <ChevronDown size={14} strokeWidth={1.5} />
            </button>

            {/* Let's go button */}
            <button
              onClick={handleSubmit}
              disabled={disabled}
              className={cn(
                'flex items-center gap-2 px-4 py-2.5 rounded-xl',
                'bg-foreground text-background',
                'text-[14px] font-medium',
                'hover:bg-foreground/90',
                'transition-all duration-200',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              <span>Let's go</span>
              <ArrowRight size={16} strokeWidth={2} />
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Standard chat input (non-welcome state)
  return (
    <div className="relative">
      {pendingFiles.length > 0 && (
        <div className="mb-2">
          <AttachmentPreviewList items={pendingFiles} onRemove={handleRemoveFile} />
        </div>
      )}
      <div className="flex items-end gap-3 p-4 bg-secondary rounded-2xl border border-border">
        {/* Plus button with menu */}
        <div className="relative">
          <button
            ref={menuButtonRef}
            onClick={() => setMenuOpen((prev) => !prev)}
            aria-label="Add attachment"
            aria-expanded={menuOpen}
            className={cn(
              'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
              'text-muted-foreground hover:text-foreground hover:bg-accent',
              'transition-all duration-200',
              menuOpen && 'bg-accent text-foreground'
            )}
          >
            <Plus size={18} strokeWidth={1.5} />
          </button>

          <ChatInputMenu
            isOpen={menuOpen}
            onClose={() => setMenuOpen(false)}
            searchEnabled={searchEnabled}
            onSearchToggle={handleSearchToggle}
            onScreenshot={handleScreenshot}
            onAddFiles={handleAddFiles}
            onAddConnector={handleAddConnector}
          />
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFilesSelected}
        />

        <div className="flex-1 flex flex-col gap-2">
          {/* Active connectors chips */}
          {activeConnectors.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {activeConnectors.map((connector) => (
                <ConnectorChip
                  key={connector.id}
                  name={connector.name}
                  onRemove={() => handleRemoveConnector(connector.id)}
                />
              ))}
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message..."
            disabled={disabled}
            rows={1}
            className={cn(
              'w-full resize-none bg-transparent py-1.5 px-1',
              'text-[14px] text-foreground leading-relaxed',
              'placeholder:text-muted-foreground',
              'focus:outline-none',
              'disabled:opacity-50'
            )}
          />
        </div>

        <button
          type="button"
          onClick={handleSubmit}
          disabled={disabled || (!value.trim() && pendingFiles.length === 0)}
          aria-label="Send message"
          className={cn(
            'w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0',
            'transition-all duration-200',
            value.trim() && !disabled
              ? 'bg-burnt text-white'
              : 'bg-accent text-muted-foreground'
          )}
        >
          <ArrowRight size={16} strokeWidth={2} />
        </button>
      </div>
    </div>
  )
}

interface PendingFile {
  id: string
  file: File
  previewUrl?: string
  kind: 'image' | 'file'
}

function AttachmentPreviewList({
  items,
  onRemove,
}: {
  items: PendingFile[]
  onRemove: (id: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          className={cn(
            'relative w-28 rounded-xl border border-border overflow-hidden',
            'bg-secondary/70'
          )}
        >
          {item.kind === 'image' && item.previewUrl ? (
            <img
              src={item.previewUrl}
              alt={item.file.name}
              className="w-full h-20 object-cover"
            />
          ) : (
            <div className="w-full h-20 flex items-center justify-center text-muted-foreground">
              <FileText size={18} />
            </div>
          )}
          <div className="px-2 py-1 text-[11px] text-muted-foreground truncate">
            {item.file.name}
          </div>
          <button
            type="button"
            onClick={() => onRemove(item.id)}
            className={cn(
              'absolute top-1 right-1 w-5 h-5 rounded-full',
              'bg-background/80 text-muted-foreground hover:text-foreground',
              'flex items-center justify-center'
            )}
            aria-label="Remove file"
          >
            <X size={12} strokeWidth={2} />
          </button>
        </div>
      ))}
    </div>
  )
}

// ============ Connector Chip Component ============

interface ConnectorChipProps {
  name: string
  onRemove: () => void
}

function ConnectorChip({ name, onRemove }: ConnectorChipProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-md',
        'bg-burnt/15 text-burnt text-[12px]',
        'border border-burnt/20'
      )}
    >
      <span className="capitalize">{name.replace(/_/g, ' ')}</span>
      <button
        onClick={onRemove}
        className="hover:text-burnt/70 transition-colors"
        aria-label={`Remove ${name}`}
      >
        <X size={12} strokeWidth={2} />
      </button>
    </span>
  )
}
