import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  email: string
  name?: string
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean

  // Actions
  setAuthenticated: (isAuthenticated: boolean) => void
  setUser: (user: User) => void
  updateUserName: (name: string) => void
  login: (user: User) => void
  logout: () => void
  setLoading: (loading: boolean) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,

      setAuthenticated: (isAuthenticated) =>
        set({
          isAuthenticated,
        }),

      setUser: (user) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...user } : user,
          isAuthenticated: true,
        })),

      updateUserName: (name) =>
        set((state) => ({
          user: state.user ? { ...state.user, name } : null,
        })),

      login: (user) =>
        set({
          user,
          isAuthenticated: true,
          isLoading: false,
        }),

      logout: () =>
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        }),

      setLoading: (isLoading) =>
        set({ isLoading }),
    }),
    {
      name: 'cowork-auth',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
