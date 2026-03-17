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
    const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB
    const ALLOWED_TEXT_EXTENSIONS = ['.txt', '.md', '.csv', '.json', '.html', '.xml']
    const ALLOWED_MIME_PREFIXES = ['text/', 'application/json', 'application/xml']

    if (file.size > MAX_FILE_SIZE) {
      const errMsg = `File too large: ${(file.size / (1024 * 1024)).toFixed(1)}MB exceeds the 10MB limit`
      setError(errMsg)
      throw new Error(errMsg)
    }

    const extension = file.name.includes('.') ? '.' + file.name.split('.').pop()!.toLowerCase() : ''
    const isAllowedExt = ALLOWED_TEXT_EXTENSIONS.includes(extension)
    const isAllowedMime = ALLOWED_MIME_PREFIXES.some((prefix) => (file.type || '').startsWith(prefix))

    if (!isAllowedExt && !isAllowedMime) {
      const errMsg = `Unsupported file type "${extension || file.type || 'unknown'}". Allowed: ${ALLOWED_TEXT_EXTENSIONS.join(', ')}`
      setError(errMsg)
      throw new Error(errMsg)
    }

    try {
      const content = await file.text()
      const result = await ingestDocument(content, file.name, file.type || 'text/plain')
      // Reload to get the full document info
      await loadDocuments()
      return result
    } catch (error) {
      console.error('Failed to upload document:', error)
      setError(error instanceof Error ? error.message : 'Failed to upload document')
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
