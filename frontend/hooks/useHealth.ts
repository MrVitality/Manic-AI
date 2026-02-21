'use client'
import { useCallback, useEffect, useRef } from 'react'
import { useChatStore } from '@/lib/store'
import { fetchServicesStatus } from '@/lib/api'

export function useHealth(pollInterval: number = 30000) {
  const { serviceStatuses, setServiceStatuses, setError } = useChatStore()
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  const loadStatus = useCallback(async () => {
    try {
      const data = await fetchServicesStatus()
      setServiceStatuses(data.services)
    } catch (error) {
      console.error('Failed to fetch service status:', error)
    }
  }, [setServiceStatuses])

  useEffect(() => {
    loadStatus()
    intervalRef.current = setInterval(loadStatus, pollInterval)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [loadStatus, pollInterval])

  return { serviceStatuses, refreshStatus: loadStatus }
}
