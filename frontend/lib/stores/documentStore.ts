import { create } from 'zustand'
import type { DocumentInfo } from '@/types'

interface DocumentState {
  documents: DocumentInfo[]
  isLoadingDocuments: boolean

  setDocuments: (documents: DocumentInfo[]) => void
  setIsLoadingDocuments: (loading: boolean) => void
  addDocument: (document: DocumentInfo) => void
  removeDocument: (id: string) => void
}

export const useDocumentStore = create<DocumentState>()((set) => ({
  documents: [],
  isLoadingDocuments: false,

  setDocuments: (documents: DocumentInfo[]) => set({ documents }),
  setIsLoadingDocuments: (loading: boolean) => set({ isLoadingDocuments: loading }),
  addDocument: (document: DocumentInfo) =>
    set((state) => ({ documents: [document, ...state.documents] })),
  removeDocument: (id: string) =>
    set((state) => ({ documents: state.documents.filter((d) => d.id !== id) })),
}))
