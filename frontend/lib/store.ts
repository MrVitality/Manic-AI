import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Conversation, Message, Model, Settings, ActiveView, DocumentInfo, ServiceStatus } from '@/types'

interface ChatState {
  conversations: Conversation[]
  currentConversationId: string | null
  currentConversation: Conversation | null
  models: Model[]
  selectedModel: string
  isLoadingModels: boolean
  isGenerating: boolean
  error: string | null
  activeView: ActiveView
  useRag: boolean
  documents: DocumentInfo[]
  isLoadingDocuments: boolean
  serviceStatuses: Record<string, ServiceStatus>
  settings: Settings

  createConversation: () => string
  deleteConversation: (id: string) => void
  selectConversation: (id: string) => void
  updateConversationTitle: (id: string, title: string) => void
  clearConversations: () => void
  addMessage: (conversationId: string, message: Message) => void
  updateMessage: (conversationId: string, messageId: string, updates: Partial<Message>) => void
  deleteMessage: (conversationId: string, messageId: string) => void
  setModels: (models: Model[]) => void
  setSelectedModel: (model: string) => void
  setIsLoadingModels: (loading: boolean) => void
  setIsGenerating: (generating: boolean) => void
  setError: (error: string | null) => void
  setActiveView: (view: ActiveView) => void
  setUseRag: (useRag: boolean) => void
  setDocuments: (documents: DocumentInfo[]) => void
  setIsLoadingDocuments: (loading: boolean) => void
  addDocument: (document: DocumentInfo) => void
  removeDocument: (id: string) => void
  setServiceStatuses: (statuses: Record<string, ServiceStatus>) => void
  updateSettings: (settings: Partial<Settings>) => void
}

const defaultSettings: Settings = {
  defaultModel: 'llama3.2:3b',
  temperature: 0.7,
  maxTokens: 2048,
  systemPrompt: 'You are a helpful AI assistant.',
  streamResponses: true,
  apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081',
  theme: 'dark',
  ragTopK: 5,
  ragThreshold: 0.7,
  accentColor: 'blue',
  fontSize: 'base',
  enableAnimations: true,
  healthCheckInterval: 30000,
  dashboardRefreshRate: 10000,
  ragBackend: 'supabase',
  ragUseHybrid: true,
}

const generateId = () => crypto.randomUUID()

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      conversations: [],
      currentConversationId: null,
      currentConversation: null,
      models: [],
      selectedModel: defaultSettings.defaultModel,
      isLoadingModels: false,
      isGenerating: false,
      error: null,
      activeView: 'chat' as ActiveView,
      useRag: false,
      documents: [],
      isLoadingDocuments: false,
      serviceStatuses: {},
      settings: defaultSettings,

      createConversation: () => {
        const id = generateId()
        const newConversation: Conversation = {
          id,
          title: 'New Chat',
          messages: [],
          model: get().selectedModel,
          createdAt: new Date(),
          updatedAt: new Date(),
        }
        set((state) => ({
          conversations: [newConversation, ...state.conversations],
          currentConversationId: id,
          currentConversation: newConversation,
        }))
        return id
      },

      deleteConversation: (id: string) => {
        set((state) => {
          const filtered = state.conversations.filter((c) => c.id !== id)
          const isCurrentDeleted = state.currentConversationId === id
          return {
            conversations: filtered,
            currentConversationId: isCurrentDeleted ? (filtered[0]?.id || null) : state.currentConversationId,
            currentConversation: isCurrentDeleted ? (filtered[0] || null) : state.currentConversation,
          }
        })
      },

      selectConversation: (id: string) => {
        set((state) => ({
          currentConversationId: id,
          currentConversation: state.conversations.find((c) => c.id === id) || null,
        }))
      },

      updateConversationTitle: (id: string, title: string) => {
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, title, updatedAt: new Date() } : c
          ),
          currentConversation: state.currentConversation?.id === id
            ? { ...state.currentConversation, title, updatedAt: new Date() }
            : state.currentConversation,
        }))
      },

      clearConversations: () => {
        set({ conversations: [], currentConversationId: null, currentConversation: null })
      },

      addMessage: (conversationId: string, message: Message) => {
        set((state) => {
          const conversations = state.conversations.map((c) => {
            if (c.id === conversationId) {
              const updatedConv = { ...c, messages: [...c.messages, message], updatedAt: new Date() }
              if (c.messages.length === 0 && message.role === 'user') {
                updatedConv.title = message.content.slice(0, 50) + (message.content.length > 50 ? '...' : '')
              }
              return updatedConv
            }
            return c
          })
          return { conversations, currentConversation: conversations.find((c) => c.id === conversationId) || null }
        })
      },

      updateMessage: (conversationId: string, messageId: string, updates: Partial<Message>) => {
        set((state) => {
          const conversations = state.conversations.map((c) => {
            if (c.id === conversationId) {
              return { ...c, messages: c.messages.map((m) => m.id === messageId ? { ...m, ...updates } : m), updatedAt: new Date() }
            }
            return c
          })
          return { conversations, currentConversation: conversations.find((c) => c.id === conversationId) || null }
        })
      },

      deleteMessage: (conversationId: string, messageId: string) => {
        set((state) => {
          const conversations = state.conversations.map((c) => {
            if (c.id === conversationId) {
              return { ...c, messages: c.messages.filter((m) => m.id !== messageId), updatedAt: new Date() }
            }
            return c
          })
          return { conversations, currentConversation: conversations.find((c) => c.id === conversationId) || null }
        })
      },

      setModels: (models: Model[]) => set({ models }),
      setSelectedModel: (model: string) => set({ selectedModel: model }),
      setIsLoadingModels: (loading: boolean) => set({ isLoadingModels: loading }),
      setIsGenerating: (generating: boolean) => set({ isGenerating: generating }),
      setError: (error: string | null) => set({ error }),
      setActiveView: (view: ActiveView) => set({ activeView: view }),
      setUseRag: (useRag: boolean) => set({ useRag }),
      setDocuments: (documents: DocumentInfo[]) => set({ documents }),
      setIsLoadingDocuments: (loading: boolean) => set({ isLoadingDocuments: loading }),
      addDocument: (document: DocumentInfo) => set((state) => ({ documents: [document, ...state.documents] })),
      removeDocument: (id: string) => set((state) => ({ documents: state.documents.filter((d) => d.id !== id) })),
      setServiceStatuses: (statuses: Record<string, ServiceStatus>) => set({ serviceStatuses: statuses }),
      updateSettings: (newSettings: Partial<Settings>) => {
        set((state) => ({ settings: { ...state.settings, ...newSettings } }))
      },
    }),
    {
      name: 'manic-ai-storage',
      partialize: (state) => ({
        conversations: state.conversations,
        currentConversationId: state.currentConversationId,
        selectedModel: state.selectedModel,
        settings: state.settings,
        useRag: state.useRag,
      }),
    }
  )
)

if (typeof window !== 'undefined') {
  const state = useChatStore.getState()
  if (state.currentConversationId) {
    const conversation = state.conversations.find((c) => c.id === state.currentConversationId)
    if (conversation) {
      useChatStore.setState({ currentConversation: conversation })
    }
  }
}
