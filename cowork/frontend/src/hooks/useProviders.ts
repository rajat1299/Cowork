import { useState, useEffect, useCallback } from 'react'
import { providers as providersApi } from '../api/coreApi'
import type { Provider, CreateProviderRequest, UpdateProviderRequest, ValidateModelRequest } from '../api/coreApi'

// ============ Predefined Provider Templates ============

export interface ProviderTemplate {
  id: string
  name: string
  description: string
  defaultEndpoint: string
  requiresApiKey: boolean
  supportedModels: string[]
}

export const PROVIDER_TEMPLATES: ProviderTemplate[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    description: 'GPT-4, GPT-3.5, and other OpenAI models',
    defaultEndpoint: 'https://api.openai.com/v1',
    requiresApiKey: true,
    supportedModels: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'],
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    description: 'Claude 3.5, Claude 3, and other Anthropic models',
    defaultEndpoint: 'https://api.anthropic.com',
    requiresApiKey: true,
    supportedModels: ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
  },
  {
    id: 'google',
    name: 'Google AI',
    description: 'Gemini Pro and other Google AI models',
    defaultEndpoint: 'https://generativelanguage.googleapis.com/v1beta',
    requiresApiKey: true,
    supportedModels: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro'],
  },
  {
    id: 'azure',
    name: 'Azure OpenAI',
    description: 'OpenAI models hosted on Azure',
    defaultEndpoint: '',
    requiresApiKey: true,
    supportedModels: ['gpt-4o', 'gpt-4', 'gpt-35-turbo'],
  },
  {
    id: 'ollama',
    name: 'Ollama (Local)',
    description: 'Run models locally with Ollama',
    defaultEndpoint: 'http://localhost:11434/v1',
    requiresApiKey: false,
    supportedModels: ['llama3.2', 'llama3.1', 'mistral', 'codellama', 'phi3'],
  },
]

// ============ Hook State ============

interface UseProvidersState {
  providers: Provider[]
  isLoading: boolean
  error: string | null
  validatingId: number | null
}

interface UseProvidersReturn extends UseProvidersState {
  // Actions
  fetchProviders: () => Promise<void>
  createProvider: (data: CreateProviderRequest) => Promise<Provider | null>
  updateProvider: (id: number, data: UpdateProviderRequest) => Promise<Provider | null>
  deleteProvider: (id: number) => Promise<boolean>
  setPreferred: (id: number) => Promise<boolean>
  validateProvider: (data: ValidateModelRequest) => Promise<{ valid: boolean; message?: string }>
  clearError: () => void
  // Helpers
  getProviderByName: (name: string) => Provider | undefined
  getPreferredProvider: () => Provider | undefined
}

// ============ Hook Implementation ============

export function useProviders(): UseProvidersReturn {
  const [state, setState] = useState<UseProvidersState>({
    providers: [],
    isLoading: false,
    error: null,
    validatingId: null,
  })

  const fetchProviders = useCallback(async () => {
    setState((s) => ({ ...s, isLoading: true, error: null }))
    try {
      const data = await providersApi.list()
      const providerList = Array.isArray(data) ? data : []
      setState((s) => ({ ...s, providers: providerList, isLoading: false }))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch providers'
      setState((s) => ({ ...s, error: message, isLoading: false }))
    }
  }, [])

  const createProvider = useCallback(async (data: CreateProviderRequest): Promise<Provider | null> => {
    setState((s) => ({ ...s, isLoading: true, error: null }))
    try {
      const provider = await providersApi.create(data)
      setState((s) => ({
        ...s,
        providers: [...s.providers, provider],
        isLoading: false,
      }))
      return provider
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create provider'
      setState((s) => ({ ...s, error: message, isLoading: false }))
      return null
    }
  }, [])

  const updateProvider = useCallback(async (id: number, data: UpdateProviderRequest): Promise<Provider | null> => {
    setState((s) => ({ ...s, isLoading: true, error: null }))
    try {
      const provider = await providersApi.update(id, data)
      setState((s) => ({
        ...s,
        providers: s.providers.map((p) => (p.id === id ? provider : p)),
        isLoading: false,
      }))
      return provider
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update provider'
      setState((s) => ({ ...s, error: message, isLoading: false }))
      return null
    }
  }, [])

  const deleteProvider = useCallback(async (id: number): Promise<boolean> => {
    setState((s) => ({ ...s, isLoading: true, error: null }))
    try {
      await providersApi.delete(id)
      setState((s) => ({
        ...s,
        providers: s.providers.filter((p) => p.id !== id),
        isLoading: false,
      }))
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete provider'
      setState((s) => ({ ...s, error: message, isLoading: false }))
      return false
    }
  }, [])

  const setPreferred = useCallback(async (id: number): Promise<boolean> => {
    setState((s) => ({ ...s, error: null }))
    try {
      await providersApi.setPreferred(id)
      // Update local state to reflect new preferred status
      setState((s) => ({
        ...s,
        providers: s.providers.map((p) => ({
          ...p,
          prefer: p.id === id,
        })),
      }))
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to set preferred provider'
      setState((s) => ({ ...s, error: message }))
      return false
    }
  }, [])

  const validateProvider = useCallback(async (data: ValidateModelRequest): Promise<{ valid: boolean; message?: string }> => {
    try {
      const result = await providersApi.validate(data)
      if (result.is_valid && result.is_tool_calls) {
        return { valid: true }
      }
      return {
        valid: false,
        message: result.message || result.error || 'Validation failed',
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Validation request failed'
      return { valid: false, message }
    }
  }, [])

  const clearError = useCallback(() => {
    setState((s) => ({ ...s, error: null }))
  }, [])

  const getProviderByName = useCallback((name: string): Provider | undefined => {
    return state.providers.find((p) => p.provider_name === name)
  }, [state.providers])

  const getPreferredProvider = useCallback((): Provider | undefined => {
    return state.providers.find((p) => p.prefer)
  }, [state.providers])

  // Fetch providers on mount
  useEffect(() => {
    fetchProviders()
  }, [fetchProviders])

  return {
    ...state,
    fetchProviders,
    createProvider,
    updateProvider,
    deleteProvider,
    setPreferred,
    validateProvider,
    clearError,
    getProviderByName,
    getPreferredProvider,
  }
}
