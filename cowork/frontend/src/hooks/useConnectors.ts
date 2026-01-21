import { useState, useEffect, useCallback } from 'react'
import { config as configApi } from '../api/coreApi'
import type { ConfigGroup, ConfigInfo, Config, CreateConfigRequest } from '../api/coreApi'

interface ConnectorState {
  groups: ConfigGroup[]
  configs: Record<string, Config[]> // keyed by group id
  isLoading: boolean
  error: string | null
}

export function useConnectors() {
  const [state, setState] = useState<ConnectorState>({
    groups: [],
    configs: {},
    isLoading: true,
    error: null,
  })

  // Fetch connector groups from /config/info
  const fetchGroups = useCallback(async () => {
    try {
      setState((s) => ({ ...s, isLoading: true, error: null }))
      const info: ConfigInfo = await configApi.getInfo()
      const groups = info.groups || []
      setState((s) => ({ ...s, groups, isLoading: false }))
    } catch (err) {
      setState((s) => ({
        ...s,
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to load connectors',
      }))
    }
  }, [])

  // Fetch configs for a specific group
  const fetchConfigsForGroup = useCallback(async (groupId: string) => {
    try {
      const configs = await configApi.list(groupId)
      setState((s) => ({
        ...s,
        configs: { ...s.configs, [groupId]: configs },
      }))
      return configs
    } catch (err) {
      console.error(`Failed to fetch configs for ${groupId}:`, err)
      return []
    }
  }, [])

  // Create a new config
  const createConfig = useCallback(
    async (data: CreateConfigRequest): Promise<Config | null> => {
      try {
        const newConfig = await configApi.create(data)
        // Refresh configs for this group
        await fetchConfigsForGroup(data.group)
        return newConfig
      } catch (err) {
        console.error('Failed to create config:', err)
        throw err
      }
    },
    [fetchConfigsForGroup]
  )

  // Update an existing config
  const updateConfig = useCallback(
    async (id: string, data: Partial<CreateConfigRequest>): Promise<Config | null> => {
      try {
        const updated = await configApi.update(id, data)
        // Refresh configs for this group
        if (data.group) {
          await fetchConfigsForGroup(data.group)
        }
        return updated
      } catch (err) {
        console.error('Failed to update config:', err)
        throw err
      }
    },
    [fetchConfigsForGroup]
  )

  // Delete a config
  const deleteConfig = useCallback(
    async (id: string, groupId: string): Promise<void> => {
      try {
        await configApi.delete(id)
        // Refresh configs for this group
        await fetchConfigsForGroup(groupId)
      } catch (err) {
        console.error('Failed to delete config:', err)
        throw err
      }
    },
    [fetchConfigsForGroup]
  )

  // Save all fields for a connector group
  const saveConnectorConfig = useCallback(
    async (
      groupId: string,
      fields: Record<string, string>
    ): Promise<void> => {
      const existingConfigs = state.configs[groupId] || []

      for (const [key, value] of Object.entries(fields)) {
        if (!value.trim()) continue // Skip empty values

        const existing = existingConfigs.find((c) => c.key === key)
        if (existing) {
          await updateConfig(existing.id, { group: groupId, key, value })
        } else {
          await createConfig({ group: groupId, key, value })
        }
      }

      // Refresh configs for this group
      await fetchConfigsForGroup(groupId)
    },
    [state.configs, createConfig, updateConfig, fetchConfigsForGroup]
  )

  // Check if a connector group has any configured fields
  const isGroupConfigured = useCallback(
    (groupId: string): boolean => {
      const configs = state.configs[groupId] || []
      return configs.length > 0
    },
    [state.configs]
  )

  // Get configured field count for a group
  const getConfiguredCount = useCallback(
    (groupId: string): number => {
      const configs = state.configs[groupId] || []
      return configs.length
    },
    [state.configs]
  )

  // Initial fetch
  useEffect(() => {
    fetchGroups()
  }, [fetchGroups])

  return {
    groups: state.groups,
    configs: state.configs,
    isLoading: state.isLoading,
    error: state.error,
    fetchGroups,
    fetchConfigsForGroup,
    createConfig,
    updateConfig,
    deleteConfig,
    saveConnectorConfig,
    isGroupConfigured,
    getConfiguredCount,
  }
}

