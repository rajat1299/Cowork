import { useState, useEffect, useCallback } from 'react'
import { mcp as mcpApi } from '../api/coreApi'
import type { McpUser, McpServer, McpUserUpdate, McpImportLocal, McpImportRemote } from '../api/coreApi'

// ============ Hook State ============

interface UseMCPState {
  userMcps: McpUser[]
  availableServers: McpServer[]
  isLoading: boolean
  error: string | null
}

interface UseMCPReturn extends UseMCPState {
  // Actions
  fetchUserMcps: () => Promise<void>
  fetchAvailableServers: (keyword?: string) => Promise<void>
  installFromRegistry: (mcpId: number) => Promise<McpUser | null>
  importLocal: (data: McpImportLocal) => Promise<boolean>
  importRemote: (data: McpImportRemote) => Promise<McpUser | null>
  updateMcp: (id: number, data: McpUserUpdate) => Promise<McpUser | null>
  deleteMcp: (id: number) => Promise<boolean>
  toggleMcp: (id: number, enabled: boolean) => Promise<boolean>
  clearError: () => void
}

// ============ Hook Implementation ============

export function useMCP(): UseMCPReturn {
  const [state, setState] = useState<UseMCPState>({
    userMcps: [],
    availableServers: [],
    isLoading: false,
    error: null,
  })

  const fetchUserMcps = useCallback(async () => {
    setState((s) => ({ ...s, isLoading: true, error: null }))
    try {
      const data = await mcpApi.listUserMcps()
      setState((s) => ({
        ...s,
        userMcps: Array.isArray(data) ? data : [],
        isLoading: false,
      }))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch MCPs'
      setState((s) => ({ ...s, error: message, isLoading: false }))
    }
  }, [])

  const fetchAvailableServers = useCallback(async (keyword?: string) => {
    try {
      const data = await mcpApi.listServers(keyword)
      setState((s) => ({
        ...s,
        availableServers: Array.isArray(data) ? data : [],
      }))
    } catch (err) {
      console.error('Failed to fetch available MCP servers:', err)
    }
  }, [])

  const installFromRegistry = useCallback(async (mcpId: number): Promise<McpUser | null> => {
    setState((s) => ({ ...s, isLoading: true, error: null }))
    try {
      const result = await mcpApi.install(mcpId)
      setState((s) => ({
        ...s,
        userMcps: [...s.userMcps, result],
        isLoading: false,
      }))
      return result
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to install MCP'
      setState((s) => ({ ...s, error: message, isLoading: false }))
      return null
    }
  }, [])

  const importLocal = useCallback(async (data: McpImportLocal): Promise<boolean> => {
    setState((s) => ({ ...s, isLoading: true, error: null }))
    try {
      await mcpApi.importLocal(data)
      // Refresh the list after import
      await fetchUserMcps()
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to import MCP'
      setState((s) => ({ ...s, error: message, isLoading: false }))
      return false
    }
  }, [fetchUserMcps])

  const importRemote = useCallback(async (data: McpImportRemote): Promise<McpUser | null> => {
    setState((s) => ({ ...s, isLoading: true, error: null }))
    try {
      const result = await mcpApi.importRemote(data)
      setState((s) => ({
        ...s,
        userMcps: [...s.userMcps, result],
        isLoading: false,
      }))
      return result
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to import remote MCP'
      setState((s) => ({ ...s, error: message, isLoading: false }))
      return null
    }
  }, [])

  const updateMcp = useCallback(async (id: number, data: McpUserUpdate): Promise<McpUser | null> => {
    setState((s) => ({ ...s, error: null }))
    try {
      const result = await mcpApi.updateUserMcp(id, data)
      setState((s) => ({
        ...s,
        userMcps: s.userMcps.map((m) => (m.id === id ? result : m)),
      }))
      return result
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update MCP'
      setState((s) => ({ ...s, error: message }))
      return null
    }
  }, [])

  const deleteMcp = useCallback(async (id: number): Promise<boolean> => {
    setState((s) => ({ ...s, error: null }))
    try {
      await mcpApi.deleteUserMcp(id)
      setState((s) => ({
        ...s,
        userMcps: s.userMcps.filter((m) => m.id !== id),
      }))
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete MCP'
      setState((s) => ({ ...s, error: message }))
      return false
    }
  }, [])

  const toggleMcp = useCallback(async (id: number, enabled: boolean): Promise<boolean> => {
    try {
      const result = await mcpApi.updateUserMcp(id, {
        status: enabled ? 'enable' : 'disable',
      })
      setState((s) => ({
        ...s,
        userMcps: s.userMcps.map((m) => (m.id === id ? result : m)),
      }))
      return true
    } catch (err) {
      console.error('Failed to toggle MCP:', err)
      return false
    }
  }, [])

  const clearError = useCallback(() => {
    setState((s) => ({ ...s, error: null }))
  }, [])

  // Fetch user MCPs on mount
  useEffect(() => {
    void fetchUserMcps() // eslint-disable-line react-hooks/set-state-in-effect
  }, [fetchUserMcps])

  return {
    ...state,
    fetchUserMcps,
    fetchAvailableServers,
    installFromRegistry,
    importLocal,
    importRemote,
    updateMcp,
    deleteMcp,
    toggleMcp,
    clearError,
  }
}

// ============ Validation Helpers ============

/**
 * Validate MCP JSON configuration format
 */
export function validateMcpJson(jsonStr: string): { valid: boolean; error?: string; data?: McpImportLocal } {
  try {
    const data = JSON.parse(jsonStr)

    if (!data.mcpServers || typeof data.mcpServers !== 'object') {
      return { valid: false, error: 'Missing or invalid "mcpServers" property' }
    }

    for (const [name, config] of Object.entries(data.mcpServers)) {
      if (!name) {
        return { valid: false, error: 'MCP server name is required' }
      }
      if (typeof config !== 'object' || config === null) {
        return { valid: false, error: `Invalid configuration for "${name}"` }
      }
      const cfg = config as Record<string, unknown>
      if (typeof cfg.command !== 'string' || !cfg.command) {
        return { valid: false, error: `Missing "command" for "${name}"` }
      }
      if (cfg.args !== undefined && !Array.isArray(cfg.args)) {
        return { valid: false, error: `Invalid "args" for "${name}" (must be array)` }
      }
      if (cfg.env !== undefined && (typeof cfg.env !== 'object' || cfg.env === null)) {
        return { valid: false, error: `Invalid "env" for "${name}" (must be object)` }
      }
    }

    return { valid: true, data: data as McpImportLocal }
  } catch {
    return { valid: false, error: 'Invalid JSON format' }
  }
}

/**
 * Default MCP JSON template
 */
export const DEFAULT_MCP_JSON = `{
  "mcpServers": {
    "example-server": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-example"],
      "env": {}
    }
  }
}`
