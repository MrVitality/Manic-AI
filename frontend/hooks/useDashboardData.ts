'use client'
import { useEffect, useCallback, useRef } from 'react'
import { useDashboardStore } from '@/lib/stores/dashboardStore'
import { uiStoreApi } from '@/lib/store'
import { useUiStore } from '@/lib/stores/uiStore'
import {
  fetchServicesStatus,
  fetchUsageAnalytics,
  fetchModelAnalytics,
  fetchRagAnalytics,
  fetchSystemInfo,
  streamServiceStatus,
  connectStatusWebSocket,
} from '@/lib/api'
import type { ServicesStatusResponse, ServiceStatus } from '@/types'

export function useDashboardData() {
  const store = useDashboardStore()
  const settings = useUiStore((s) => s.settings)
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

  const applyServiceData = useCallback((data: Partial<ServicesStatusResponse>) => {
    if (!data.services) return
    const snapshot = {
      timestamp: data.timestamp || new Date().toISOString(),
      services: {} as Record<string, { status: ServiceStatus['status']; latency_ms: ServiceStatus['latency_ms'] }>,
    }
    for (const [key, svc] of Object.entries(data.services)) {
      snapshot.services[key] = { status: svc.status, latency_ms: svc.latency_ms }
    }
    addServiceSnapshot(snapshot)
    uiStoreApi.getState().setServiceStatuses(data.services)
  }, [addServiceSnapshot])

  const refreshServices = useCallback(async () => {
    try {
      const data = await fetchServicesStatus()
      applyServiceData(data)
    } catch (e) {
      console.error('Failed to refresh services:', e)
      setError('Failed to refresh services')
    }
  }, [applyServiceData, setError])

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

  // WebSocket connection for live service status (with SSE fallback)
  useEffect(() => {
    let ws: WebSocket | null = null
    let reconnectTimeout: ReturnType<typeof setTimeout>
    let usingSse = false

    const connectWs = () => {
      try {
        ws = connectStatusWebSocket(
          (data) => {
            applyServiceData(data)
            setIsStreaming(true)
          },
          () => {
            // WebSocket error — reconnect after 5s
            setIsStreaming(false)
            reconnectTimeout = setTimeout(connectWs, 5000)
          },
        )

        // Override the onclose set inside connectStatusWebSocket so we can also
        // clear the ping interval (handled inside) AND schedule a reconnect.
        const originalOnClose = ws.onclose
        ws.onclose = (event) => {
          originalOnClose?.call(ws!, event)
          setIsStreaming(false)
          // Only reconnect on unexpected closes (not a clean teardown from cleanup)
          if (!event.wasClean) {
            reconnectTimeout = setTimeout(connectWs, 5000)
          }
        }
      } catch {
        // WebSocket constructor unavailable — fall back to SSE
        if (!usingSse) {
          usingSse = true
          connectSse()
        }
      }
    }

    const connectSse = () => {
      try {
        const sse = streamServiceStatus()
        sseRef.current = sse

        sse.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            applyServiceData(data)
            setIsStreaming(true)
          } catch {}
        }

        sse.onerror = () => {
          setIsStreaming(false)
        }
      } catch {
        // SSE also unavailable — polling fallback will handle it
      }
    }

    connectWs()

    return () => {
      clearTimeout(reconnectTimeout)
      if (ws) {
        // Signal a clean close so onclose does not schedule a reconnect
        const prev = ws.onclose
        ws.onclose = null
        ws.close()
        ws.onclose = prev
      }
      if (sseRef.current) {
        sseRef.current.close()
        sseRef.current = null
      }
    }
  }, [applyServiceData, setIsStreaming])

  // Subscribe to isStreaming directly to avoid stale closure
  const isStreaming = useDashboardStore((s) => s.isStreaming)

  // One-time analytics fetch on mount
  const analyticsInitialized = useRef(false)
  useEffect(() => {
    if (!analyticsInitialized.current) {
      analyticsInitialized.current = true
      refreshAnalytics()
    }
  }, [refreshAnalytics])

  // Polling fallback for service status when not streaming (separate from analytics)
  useEffect(() => {
    if (!isStreaming) {
      refreshServices()
      const interval = setInterval(refreshServices, settings.dashboardRefreshRate)
      return () => clearInterval(interval)
    }
  }, [refreshServices, isStreaming, settings.dashboardRefreshRate])

  return {
    ...store,
    refreshAll,
    refreshServices,
    refreshAnalytics,
  }
}
