import { create } from 'zustand'
import type {
  DashboardTab,
  ServiceHealthSnapshot,
  UsageAnalyticsData,
  ModelAnalyticsData,
  RagAnalyticsData,
  SystemInfo,
} from '@/types'

interface DashboardState {
  dashboardTab: DashboardTab
  setDashboardTab: (tab: DashboardTab) => void

  serviceHistory: ServiceHealthSnapshot[]
  addServiceSnapshot: (snapshot: ServiceHealthSnapshot) => void
  clearServiceHistory: () => void

  usageAnalytics: UsageAnalyticsData | null
  modelAnalytics: ModelAnalyticsData | null
  ragAnalytics: RagAnalyticsData | null
  isLoadingAnalytics: boolean
  setUsageAnalytics: (data: UsageAnalyticsData) => void
  setModelAnalytics: (data: ModelAnalyticsData) => void
  setRagAnalytics: (data: RagAnalyticsData) => void
  setIsLoadingAnalytics: (loading: boolean) => void

  systemInfo: SystemInfo | null
  setSystemInfo: (info: SystemInfo) => void

  isStreaming: boolean
  setIsStreaming: (streaming: boolean) => void

  lastRefresh: Date | null
  setLastRefresh: (date: Date) => void

  error: string | null
  setError: (error: string | null) => void
}

const MAX_HISTORY = 100

export const useDashboardStore = create<DashboardState>()((set) => ({
  dashboardTab: 'overview',
  setDashboardTab: (tab) => set({ dashboardTab: tab }),

  serviceHistory: [],
  addServiceSnapshot: (snapshot) =>
    set((state) => ({
      serviceHistory: [...state.serviceHistory.slice(-(MAX_HISTORY - 1)), snapshot],
    })),
  clearServiceHistory: () => set({ serviceHistory: [] }),

  usageAnalytics: null,
  modelAnalytics: null,
  ragAnalytics: null,
  isLoadingAnalytics: false,
  setUsageAnalytics: (data) => set({ usageAnalytics: data }),
  setModelAnalytics: (data) => set({ modelAnalytics: data }),
  setRagAnalytics: (data) => set({ ragAnalytics: data }),
  setIsLoadingAnalytics: (loading) => set({ isLoadingAnalytics: loading }),

  systemInfo: null,
  setSystemInfo: (info) => set({ systemInfo: info }),

  isStreaming: false,
  setIsStreaming: (streaming) => set({ isStreaming: streaming }),

  lastRefresh: null,
  setLastRefresh: (date) => set({ lastRefresh: date }),

  error: null,
  setError: (error) => set({ error }),
}))
