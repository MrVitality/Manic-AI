// =============================================================================
// Manic AI - Unified Store (barrel re-export for backward compatibility)
// =============================================================================
//
// The monolithic store has been split into focused stores:
//   - conversationStore: conversations, currentConversationId, CRUD
//   - modelStore: models, selectedModel
//   - documentStore: documents
//   - uiStore: isGenerating, error, sidebarCollapsed, settings, useRag
//   - commandPaletteStore: command palette UI state
//   - dashboardStore: dashboard analytics
//   - ragStore: RAG center state
//
// This file provides a backward-compatible `useChatStore` that composes
// all the split stores so existing components continue to work without changes.
// New code should import from the individual stores directly.
// =============================================================================

import { useConversationStore } from '@/lib/stores/conversationStore'
import { useModelStore } from '@/lib/stores/modelStore'
import { useDocumentStore } from '@/lib/stores/documentStore'
import { useUiStore } from '@/lib/stores/uiStore'
import type { Conversation, Message, Model, Settings, DocumentInfo, ServiceStatus } from '@/types'

// Backward-compatible composed hook
// Components that already use `useChatStore` will keep working.
export function useChatStore() {
  const conversationState = useConversationStore()
  const modelState = useModelStore()
  const documentState = useDocumentStore()
  const uiState = useUiStore()

  // Derived: currentConversation — use a stable selector to avoid a new object
  // reference on every render when nothing has actually changed.
  const currentConversation = useConversationStore(
    (s) => s.currentConversationId
      ? s.conversations.find((c) => c.id === s.currentConversationId) ?? null
      : null
  )

  return {
    // Conversation state
    conversations: conversationState.conversations,
    currentConversationId: conversationState.currentConversationId,
    currentConversation,
    createConversation: () => conversationState.createConversation(modelState.selectedModel),
    deleteConversation: conversationState.deleteConversation,
    selectConversation: conversationState.selectConversation,
    updateConversationTitle: conversationState.updateConversationTitle,
    clearConversations: conversationState.clearConversations,
    addMessage: conversationState.addMessage,
    updateMessage: conversationState.updateMessage,
    deleteMessage: conversationState.deleteMessage,

    // Model state
    models: modelState.models,
    selectedModel: modelState.selectedModel,
    isLoadingModels: modelState.isLoadingModels,
    setModels: modelState.setModels,
    setSelectedModel: modelState.setSelectedModel,
    setIsLoadingModels: modelState.setIsLoadingModels,

    // Document state
    documents: documentState.documents,
    isLoadingDocuments: documentState.isLoadingDocuments,
    setDocuments: documentState.setDocuments,
    setIsLoadingDocuments: documentState.setIsLoadingDocuments,
    addDocument: documentState.addDocument,
    removeDocument: documentState.removeDocument,

    // UI state
    isGenerating: uiState.isGenerating,
    error: uiState.error,
    useRag: uiState.useRag,
    useAgentMode: uiState.useAgentMode,
    serviceStatuses: uiState.serviceStatuses,
    settings: uiState.settings,
    setIsGenerating: uiState.setIsGenerating,
    setError: uiState.setError,
    setUseRag: uiState.setUseRag,
    setUseAgentMode: uiState.setUseAgentMode,
    setServiceStatuses: uiState.setServiceStatuses,
    updateSettings: uiState.updateSettings,
  }
}

// Re-export individual stores for new code
export { useConversationStore } from '@/lib/stores/conversationStore'
export { useModelStore } from '@/lib/stores/modelStore'
export { useDocumentStore } from '@/lib/stores/documentStore'
export { useUiStore } from '@/lib/stores/uiStore'
export { useCommandPaletteStore } from '@/lib/stores/commandPaletteStore'
export { useDashboardStore } from '@/lib/stores/dashboardStore'
export { useRagStore } from '@/lib/stores/ragStore'
export { useArtifactStore } from '@/lib/stores/artifactStore'

// Static access for non-hook contexts (e.g., inside callbacks)
// Usage: chatStoreApi.getState().conversations
export const conversationStoreApi = useConversationStore
export const modelStoreApi = useModelStore
export const documentStoreApi = useDocumentStore
export const uiStoreApi = useUiStore
