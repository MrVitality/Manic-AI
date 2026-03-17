'use client'
import { useCallback, useEffect, useRef } from 'react'
import { useChatStore } from '@/lib/store'
import { useDashboardStore } from '@/lib/stores/dashboardStore'
import { fetchServicesStatus } from '@/lib/api'

export function useHealth(pollInterval: number = 30000) {
  const { serviceStatuses, setServiceStatuses, setError } = useChatStore()
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  // Check if dashboard SSE is already streaming — avoid redundant polling
  const isStreaming = useDashboardStore((s) => s.isStreaming)

  const loadStatus = useCallback(async () => {
    try {
      const data = await fetchServicesStatus()
      setServiceStatuses(data.services)
    } catch (error) {
      console.error('Failed to fetch service status:', error)
    }
  }, [setServiceStatuses])

  useEffect(() => {
    // Always do an initial fetch
    loadStatus()

    // Only poll if SSE is not actively streaming service data
    if (!isStreaming) {
      intervalRef.current = setInterval(loadStatus, pollInterval)
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [loadStatus, pollInterval, isStreaming])

  return { serviceStatuses, refreshStatus: loadStatus }
}
