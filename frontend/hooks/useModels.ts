'use client'

import { useEffect } from 'react'
import useSWR from 'swr'
import { useChatStore } from '@/lib/store'
import { fetchModels } from '@/lib/api'

export function useModels() {
  const { models, selectedModel, setModels, setSelectedModel, setError } = useChatStore()

  const { data, isLoading, mutate } = useSWR('models', fetchModels, {
    refreshInterval: 30_000,
    dedupingInterval: 5_000,
    onError: () => {
      setError("Failed to connect to Ollama. Make sure it's running.")
    },
  })

  // Sync SWR data to Zustand store after each successful fetch
  useEffect(() => {
    if (!data) return
    setModels(data)
    if (data.length > 0 && !data.some((m) => m.name === selectedModel)) {
      setSelectedModel(data[0].name)
    }
  }, [data, selectedModel, setModels, setSelectedModel])

  return {
    models,
    selectedModel,
    isLoadingModels: isLoading,
    setSelectedModel,
    refreshModels: () => mutate(),
  }
}
