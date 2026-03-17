import { create } from 'zustand'
import type {
  RagCenterTab,
  CollectionInfo,
  ChunkInfo,
  SearchConfig,
  SearchExplainResult,
  RagStatsData,
} from '@/types'

interface RagState {
  ragTab: RagCenterTab
  setRagTab: (tab: RagCenterTab) => void

  collections: CollectionInfo[]
  isLoadingCollections: boolean
  setCollections: (collections: CollectionInfo[]) => void
  setIsLoadingCollections: (loading: boolean) => void

  searchQuery: string
  searchResults: SearchExplainResult[]
  searchLatency: number | null
  searchConfig: SearchConfig
  isSearching: boolean
  setSearchQuery: (query: string) => void
  setSearchResults: (results: SearchExplainResult[]) => void
  setSearchLatency: (latency: number | null) => void
  setSearchConfig: (config: Partial<SearchConfig>) => void
  setIsSearching: (searching: boolean) => void

  selectedDocumentId: string | null
  documentChunks: ChunkInfo[]
  isLoadingChunks: boolean
  totalChunks: number
  setSelectedDocumentId: (id: string | null) => void
  setDocumentChunks: (chunks: ChunkInfo[]) => void
  setIsLoadingChunks: (loading: boolean) => void
  setTotalChunks: (total: number) => void

  ragStats: RagStatsData | null
  isLoadingStats: boolean
  setRagStats: (stats: RagStatsData) => void
  setIsLoadingStats: (loading: boolean) => void

  error: string | null
  setError: (error: string | null) => void
}

export const useRagStore = create<RagState>()((set) => ({
  ragTab: 'pipeline',
  setRagTab: (tab) => set({ ragTab: tab }),

  collections: [],
  isLoadingCollections: false,
  setCollections: (collections) => set({ collections }),
  setIsLoadingCollections: (loading) => set({ isLoadingCollections: loading }),

  searchQuery: '',
  searchResults: [],
  searchLatency: null,
  searchConfig: {
    topK: 5,
    threshold: 0.7,
    useHybrid: true,
    backend: 'supabase',
    collectionId: null,
    includeVectors: false,
  },
  isSearching: false,
  setSearchQuery: (query) => set({ searchQuery: query }),
  setSearchResults: (results) => set({ searchResults: results }),
  setSearchLatency: (latency) => set({ searchLatency: latency }),
  setSearchConfig: (config) =>
    set((state) => ({ searchConfig: { ...state.searchConfig, ...config } })),
  setIsSearching: (searching) => set({ isSearching: searching }),

  selectedDocumentId: null,
  documentChunks: [],
  isLoadingChunks: false,
  totalChunks: 0,
  setSelectedDocumentId: (id) => set({ selectedDocumentId: id, documentChunks: [], totalChunks: 0 }),
  setDocumentChunks: (chunks) => set({ documentChunks: chunks }),
  setIsLoadingChunks: (loading) => set({ isLoadingChunks: loading }),
  setTotalChunks: (total) => set({ totalChunks: total }),

  ragStats: null,
  isLoadingStats: false,
  setRagStats: (stats) => set({ ragStats: stats }),
  setIsLoadingStats: (loading) => set({ isLoadingStats: loading }),

  error: null,
  setError: (error) => set({ error }),
}))
