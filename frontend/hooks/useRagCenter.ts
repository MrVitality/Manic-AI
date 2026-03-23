'use client'
import { useEffect, useCallback } from 'react'
import { useRagStore } from '@/lib/stores/ragStore'
import {
  fetchRagStats,
  fetchCollections,
  fetchDocumentChunks,
  searchExplain,
} from '@/lib/api'
import type { SearchConfig } from '@/types'

export function useRagCenter() {
  const store = useRagStore()

  // Zustand setters are stable references — safe to use without deps
  const setRagStats = useRagStore((s) => s.setRagStats)
  const setCollections = useRagStore((s) => s.setCollections)
  const setSelectedDocumentId = useRagStore((s) => s.setSelectedDocumentId)
  const setIsLoadingChunks = useRagStore((s) => s.setIsLoadingChunks)
  const setDocumentChunks = useRagStore((s) => s.setDocumentChunks)
  const setTotalChunks = useRagStore((s) => s.setTotalChunks)
  const setIsSearching = useRagStore((s) => s.setIsSearching)
  const setSearchQuery = useRagStore((s) => s.setSearchQuery)
  const setSearchResults = useRagStore((s) => s.setSearchResults)
  const setSearchLatency = useRagStore((s) => s.setSearchLatency)
  const setError = useRagStore((s) => s.setError)

  const refreshStats = useCallback(async () => {
    try {
      const stats = await fetchRagStats()
      setRagStats(stats)
    } catch (e) {
      console.error('Failed to fetch RAG stats:', e)
      setError('Failed to fetch RAG stats')
    }
  }, [setRagStats, setError])

  const refreshCollections = useCallback(async () => {
    try {
      const collections = await fetchCollections()
      setCollections(collections)
    } catch (e) {
      console.error('Failed to fetch collections:', e)
      setError('Failed to fetch collections')
    }
  }, [setCollections, setError])

  const loadChunks = useCallback(async (documentId: string, limit = 50, offset = 0) => {
    setSelectedDocumentId(documentId)
    setIsLoadingChunks(true)
    try {
      const data = await fetchDocumentChunks(documentId, limit, offset)
      setDocumentChunks(data.chunks)
      setTotalChunks(data.total)
    } catch (e) {
      console.error('Failed to fetch chunks:', e)
      setError('Failed to fetch document chunks')
    } finally {
      setIsLoadingChunks(false)
    }
  }, [setSelectedDocumentId, setIsLoadingChunks, setDocumentChunks, setTotalChunks, setError])

  const performSearch = useCallback(async (query: string, config: SearchConfig) => {
    if (!query.trim()) return
    setIsSearching(true)
    setSearchQuery(query)
    try {
      const response = await searchExplain({
        query,
        top_k: config.topK,
        threshold: config.threshold,
        use_hybrid: config.useHybrid,
        collection_id: config.collectionId,
        include_vectors: config.includeVectors,
        backend: config.backend,
        rerank: config.rerank,
        keyword_weight: config.useHybrid ? config.keywordWeight : undefined,
      })
      setSearchResults(response.results)
      setSearchLatency(response.search_latency_ms)
    } catch (e) {
      console.error('Search failed:', e)
      setSearchResults([])
      setError('Search failed')
    } finally {
      setIsSearching(false)
    }
  }, [setIsSearching, setSearchQuery, setSearchResults, setSearchLatency, setError])

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshStats(), refreshCollections()])
  }, [refreshStats, refreshCollections])

  useEffect(() => {
    refreshAll()
  }, [refreshAll])

  return {
    ...store,
    refreshStats,
    refreshCollections,
    loadChunks,
    performSearch,
    refreshAll,
  }
}
