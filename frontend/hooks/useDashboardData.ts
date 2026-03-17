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

  // Zustand setters are stable references — safe to use without deps
  const addServiceSnapshot = useDashboardStore((s) => s.addServiceSnapshot)
  const setIsLoadingAnalytics = useDashboardStore((s) => s.setIsLoadingAnalytics)
  const setUsageAnalytics = useDashboardStore((s) => s.setUsageAnalytics)
  const setModelAnalytics = useDashboardStore((s) => s.setModelAnalytics)
  const setRagAnalytics = useDashboardStore((s) => s.setRagAnalytics)
  const setSystemInfo = useDashboardStore((s) => s.setSystemInfo)
  const setLastRefresh = useDashboardStore((s) => s.setLastRefresh)
  const setIsStreaming = useDashboardStore((s) => s.setIsStreaming)
  const setError = useDashboardStore((s) => s.setError)

  const refreshServices = useCallback(async () => {
    try {
      const data = await fetchServicesStatus()
      const snapshot = { timestamp: data.timestamp, services: {} as Record<string, { status: any; latency_ms: any }> }
      for (const [key, svc] of Object.entries(data.services)) {
        snapshot.services[key] = { status: svc.status, latency_ms: svc.latency_ms }
      }
      addServiceSnapshot(snapshot)
      useChatStore.getState().setServiceStatuses(data.services)
    } catch (e) {
      console.error('Failed to refresh services:', e)
      setError('Failed to refresh services')
    }
  }, [addServiceSnapshot, setError])

  const refreshAnalytics = useCallback(async () => {
    setIsLoadingAnalytics(true)
    try {
      const [usage, models, rag, sysInfo] = await Promise.allSettled([
        fetchUsageAnalytics('day'),
        fetchModelAnalytics(),
        fetchRagAnalytics(),
        fetchSystemInfo(),
      ])
      if (usage.status === 'fulfilled') setUsageAnalytics(usage.value)
      if (models.status === 'fulfilled') setModelAnalytics(models.value)
      if (rag.status === 'fulfilled') setRagAnalytics(rag.value)
      if (sysInfo.status === 'fulfilled') setSystemInfo(sysInfo.value)
      setLastRefresh(new Date())
    } catch (e) {
      console.error('Failed to refresh analytics:', e)
      setError('Failed to refresh analytics')
    } finally {
      setIsLoadingAnalytics(false)
    }
  }, [setIsLoadingAnalytics, setUsageAnalytics, setModelAnalytics, setRagAnalytics, setSystemInfo, setLastRefresh, setError])

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
            addServiceSnapshot(snapshot)
            useChatStore.getState().setServiceStatuses(data.services)
            setIsStreaming(true)
          }
        } catch {}
      }

      sse.onerror = () => {
        setIsStreaming(false)
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
  }, [addServiceSnapshot, setIsStreaming])

  // Polling fallback
  useEffect(() => {
    refreshAll()
    const interval = setInterval(refreshServices, settings.dashboardRefreshRate)
    return () => clearInterval(interval)
  }, [refreshAll, refreshServices, settings.dashboardRefreshRate])

  return {
    ...store,
    refreshAll,
    refreshServices,
    refreshAnalytics,
  }
}
