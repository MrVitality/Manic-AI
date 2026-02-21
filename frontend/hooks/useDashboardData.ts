'use client'
import { useEffect, useCallback, useRef } from 'react'
import { useDashboardStore } from '@/lib/stores/dashboardStore'
import { useChatStore } from '@/lib/store'
import {
  fetchServicesStatus,
  fetchUsageAnalytics,
  fetchModelAnalytics,
  fetchRagAnalytics,
  fetchSystemInfo,
  streamServiceStatus,
} from '@/lib/api'

export function useDashboardData() {
  const store = useDashboardStore()
  const settings = useChatStore((s) => s.settings)
  const sseRef = useRef<EventSource | null>(null)

  const refreshServices = useCallback(async () => {
    try {
      const data = await fetchServicesStatus()
      const snapshot = { timestamp: data.timestamp, services: {} as Record<string, { status: any; latency_ms: any }> }
      for (const [key, svc] of Object.entries(data.services)) {
        snapshot.services[key] = { status: svc.status, latency_ms: svc.latency_ms }
      }
      store.addServiceSnapshot(snapshot)
      useChatStore.getState().setServiceStatuses(data.services)
    } catch (e) {
      console.error('Failed to refresh services:', e)
    }
  }, [])

  const refreshAnalytics = useCallback(async () => {
    store.setIsLoadingAnalytics(true)
    try {
      const [usage, models, rag, sysInfo] = await Promise.allSettled([
        fetchUsageAnalytics('day'),
        fetchModelAnalytics(),
        fetchRagAnalytics(),
        fetchSystemInfo(),
      ])
      if (usage.status === 'fulfilled') store.setUsageAnalytics(usage.value)
      if (models.status === 'fulfilled') store.setModelAnalytics(models.value)
      if (rag.status === 'fulfilled') store.setRagAnalytics(rag.value)
      if (sysInfo.status === 'fulfilled') store.setSystemInfo(sysInfo.value)
      store.setLastRefresh(new Date())
    } catch (e) {
      console.error('Failed to refresh analytics:', e)
    } finally {
      store.setIsLoadingAnalytics(false)
    }
  }, [])

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshServices(), refreshAnalytics()])
  }, [refreshServices, refreshAnalytics])

  // SSE connection for live service status
  useEffect(() => {
    try {
      const sse = streamServiceStatus()
      sseRef.current = sse

      sse.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.services) {
            const snapshot = { timestamp: data.timestamp || new Date().toISOString(), services: {} as Record<string, { status: any; latency_ms: any }> }
            for (const [key, svc] of Object.entries(data.services) as any) {
              snapshot.services[key] = { status: svc.status, latency_ms: svc.latency_ms }
            }
            store.addServiceSnapshot(snapshot)
            useChatStore.getState().setServiceStatuses(data.services)
            store.setIsStreaming(true)
          }
        } catch {}
      }

      sse.onerror = () => {
        store.setIsStreaming(false)
      }
    } catch {
      // SSE not available, fall back to polling
    }

    return () => {
      if (sseRef.current) {
        sseRef.current.close()
        sseRef.current = null
      }
    }
  }, [])

  // Polling fallback
  useEffect(() => {
    refreshAll()
    const interval = setInterval(refreshServices, settings.dashboardRefreshRate)
    return () => clearInterval(interval)
  }, [settings.dashboardRefreshRate])

  return {
    ...store,
    refreshAll,
    refreshServices,
    refreshAnalytics,
  }
}
