'use client'
import { useCallback, useEffect } from 'react'
import { useChatStore } from '@/lib/store'
import { fetchDocuments, ingestDocument, deleteDocument as apiDeleteDocument } from '@/lib/api'

export function useDocuments() {
  const { documents, isLoadingDocuments, setDocuments, setIsLoadingDocuments, addDocument, removeDocument, setError } = useChatStore()

  const loadDocuments = useCallback(async () => {
    setIsLoadingDocuments(true)
    try {
      const docs = await fetchDocuments()
      setDocuments(docs)
    } catch (error) {
      console.error('Failed to fetch documents:', error)
      setError('Failed to load documents')
    } finally {
      setIsLoadingDocuments(false)
    }
  }, [setDocuments, setIsLoadingDocuments, setError])

  const uploadDocument = useCallback(async (file: File) => {
    try {
      const content = await file.text()
      const result = await ingestDocument(content, file.name, file.type || 'text/plain')
      // Reload to get the full document info
      await loadDocuments()
      return result
    } catch (error) {
      console.error('Failed to upload document:', error)
      setError('Failed to upload document')
      throw error
    }
  }, [loadDocuments, setError])

  const deleteDoc = useCallback(async (id: string) => {
    try {
      await apiDeleteDocument(id)
      removeDocument(id)
    } catch (error) {
      console.error('Failed to delete document:', error)
      setError('Failed to delete document')
      throw error
    }
  }, [removeDocument, setError])

  useEffect(() => {
    loadDocuments()
  }, [loadDocuments])

  return { documents, isLoadingDocuments, loadDocuments, uploadDocument, deleteDocument: deleteDoc }
}
