import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Settings, ServiceStatus } from '@/types'

const HEALTH_CHECK_INTERVAL_MS = 30_000
const DASHBOARD_REFRESH_INTERVAL_MS = 10_000

const defaultSettings: Settings = {
  defaultModel: 'llama3.2:3b',
  temperature: 0.7,
  maxTokens: 2048,
  systemPrompt: 'You are a helpful AI assistant.',
  streamResponses: true,
  apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081',
  theme: 'dark',
  ragTopK: 5,
  ragThreshold: 0.7,
  accentColor: 'blue',
  fontSize: 'base',
  enableAnimations: true,
  healthCheckInterval: HEALTH_CHECK_INTERVAL_MS,
  dashboardRefreshRate: DASHBOARD_REFRESH_INTERVAL_MS,
  ragBackend: 'supabase',
  ragUseHybrid: true,
}

interface UiState {
  isGenerating: boolean
  error: string | null
  sidebarCollapsed: boolean
  useRag: boolean
  serviceStatuses: Record<string, ServiceStatus>
  settings: Settings

  setIsGenerating: (generating: boolean) => void
  setError: (error: string | null) => void
  setSidebarCollapsed: (collapsed: boolean) => void
  toggleSidebar: () => void
  setUseRag: (useRag: boolean) => void
  setServiceStatuses: (statuses: Record<string, ServiceStatus>) => void
  updateSettings: (settings: Partial<Settings>) => void
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      isGenerating: false,
      error: null,
      sidebarCollapsed: false,
      useRag: false,
      serviceStatuses: {},
      settings: defaultSettings,

      setIsGenerating: (generating: boolean) => set({ isGenerating: generating }),
      setError: (error: string | null) => set({ error }),
      setSidebarCollapsed: (collapsed: boolean) => set({ sidebarCollapsed: collapsed }),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setUseRag: (useRag: boolean) => set({ useRag }),
      setServiceStatuses: (statuses: Record<string, ServiceStatus>) =>
        set({ serviceStatuses: statuses }),
      updateSettings: (newSettings: Partial<Settings>) =>
        set((state) => ({ settings: { ...state.settings, ...newSettings } })),
    }),
    {
      name: 'manic-ai-ui',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        settings: state.settings,
        useRag: state.useRag,
      }),
    }
  )
)
