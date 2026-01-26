import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type ThemeMode = 'system' | 'light' | 'dark'

interface ThemeState {
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
}

/**
 * Get the effective theme based on mode and system preference
 */
function getEffectiveTheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return mode
}

/**
 * Apply theme to document
 */
function applyTheme(mode: ThemeMode) {
  const effectiveTheme = getEffectiveTheme(mode)
  const root = document.documentElement

  if (effectiveTheme === 'light') {
    root.classList.add('light')
    document.body.classList.add('light')
  } else {
    root.classList.remove('light')
    document.body.classList.remove('light')
  }
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      mode: 'system',

      setMode: (mode) => {
        applyTheme(mode)
        set({ mode })
      },
    }),
    {
      name: 'cowork-theme',
      onRehydrateStorage: () => (state) => {
        // Apply theme on rehydration
        if (state) {
          applyTheme(state.mode)
        }
      },
    }
  )
)

// Listen for system theme changes
if (typeof window !== 'undefined') {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const { mode } = useThemeStore.getState()
    if (mode === 'system') {
      applyTheme('system')
    }
  })

  // Apply initial theme
  const { mode } = useThemeStore.getState()
  applyTheme(mode)
}

