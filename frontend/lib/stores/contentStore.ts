import { create } from 'zustand'
import type { ContentEntry, ContentFilter } from '@/types'

interface ContentState {
  entries: ContentEntry[]
  total: number
  isLoading: boolean
  error: string | null

  filter: ContentFilter
  setFilter: (filter: Partial<ContentFilter>) => void

  selectedEntry: ContentEntry | null
  isLoadingDetail: boolean
  setSelectedEntry: (entry: ContentEntry | null) => void
  setIsLoadingDetail: (loading: boolean) => void

  setEntries: (entries: ContentEntry[], total: number) => void
  upsertEntry: (entry: ContentEntry) => void
  removeEntry: (id: string) => void
  setIsLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const useContentStore = create<ContentState>()((set) => ({
  entries: [],
  total: 0,
  isLoading: false,
  error: null,

  filter: {
    status: null,
    platform: null,
    listing_id: null,
    start_date: null,
    end_date: null,
    limit: 100,
    offset: 0,
  },
  setFilter: (filter) => set((state) => ({ filter: { ...state.filter, ...filter } })),

  selectedEntry: null,
  isLoadingDetail: false,
  setSelectedEntry: (entry) => set({ selectedEntry: entry }),
  setIsLoadingDetail: (loading) => set({ isLoadingDetail: loading }),

  setEntries: (entries, total) => set({ entries, total }),
  upsertEntry: (entry) =>
    set((state) => {
      const idx = state.entries.findIndex((e) => e.id === entry.id)
      if (idx === -1) return { entries: [entry, ...state.entries] }
      const next = state.entries.slice()
      next[idx] = entry
      return { entries: next }
    }),
  removeEntry: (id) =>
    set((state) => ({
      entries: state.entries.filter((e) => e.id !== id),
      total: Math.max(0, state.total - 1),
    })),
  setIsLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}))
