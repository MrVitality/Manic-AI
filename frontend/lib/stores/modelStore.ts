import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Model } from '@/types'

interface ModelState {
  models: Model[]
  selectedModel: string
  isLoadingModels: boolean

  setModels: (models: Model[]) => void
  setSelectedModel: (model: string) => void
  setIsLoadingModels: (loading: boolean) => void
}

export const useModelStore = create<ModelState>()(
  persist(
    (set) => ({
      models: [],
      selectedModel: 'llama3.2:3b',
      isLoadingModels: false,

      setModels: (models: Model[]) => set({ models }),
      setSelectedModel: (model: string) => set({ selectedModel: model }),
      setIsLoadingModels: (loading: boolean) => set({ isLoadingModels: loading }),
    }),
    {
      name: 'manic-ai-models',
      partialize: (state) => ({
        selectedModel: state.selectedModel,
      }),
    }
  )
)
