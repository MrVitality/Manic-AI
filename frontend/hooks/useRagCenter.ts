'use client'
import { useEffect, useCallback } from 'react'
import { useRagStore } from '@/lib/stores/ragStore'
import {
  fetchRagStats,
  fetchCollections,
  fetchDocuments,
  fetchDocumentChunks,
  searchExplain,
} from '@/lib/api'
import type { SearchConfig } from '@/types'

export function useRagCenter() {
  const store = useRagStore()

  const refreshStats = useCallback(async () => {
    try {
      const stats = await fetchRagStats()
      store.setRagStats(stats)
    } catch (e) {
      console.error('Failed to fetch RAG stats:', e)
    }
  }, [])

  const refreshCollections = useCallback(async () => {
    try {
      const collections = await fetchCollections()
      store.setCollections(collections)
    } catch (e) {
      console.error('Failed to fetch collections:', e)
    }
  }, [])

  const loadChunks = useCallback(async (documentId: string, limit = 50, offset = 0) => {
    store.setSelectedDocumentId(documentId)
    store.setIsLoadingChunks(true)
    try {
      const data = await fetchDocumentChunks(documentId, limit, offset)
      store.setDocumentChunks(data.chunks)
      store.setTotalChunks(data.total)
    } catch (e) {
      console.error('Failed to fetch chunks:', e)
    } finally {
      store.setIsLoadingChunks(false)
    }
  }, [])

  const performSearch = useCallback(async (query: string, config: SearchConfig) => {
    if (!query.trim()) return
    store.setIsSearching(true)
    store.setSearchQuery(query)
    try {
      const response = await searchExplain({
        query,
        top_k: config.topK,
        threshold: config.threshold,
        use_hybrid: config.useHybrid,
        collection_id: config.collectionId,
        include_vectors: config.includeVectors,
        backend: config.backend,
      })
      store.setSearchResults(response.results)
      store.setSearchLatency(response.search_latency_ms)
    } catch (e) {
      console.error('Search failed:', e)
      store.setSearchResults([])
    } finally {
      store.setIsSearching(false)
    }
  }, [])

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshStats(), refreshCollections()])
  }, [refreshStats, refreshCollections])

  useEffect(() => {
    refreshAll()
  }, [])

  return {
    ...store,
    refreshStats,
    refreshCollections,
    loadChunks,
    performSearch,
    refreshAll,
  }
}
