import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Conversation, Message } from '@/types'

const generateId = () => crypto.randomUUID()

interface ConversationState {
  conversations: Conversation[]
  currentConversationId: string | null

  // Derived selector — use this instead of storing currentConversation
  getCurrentConversation: () => Conversation | null

  createConversation: (model?: string) => string
  deleteConversation: (id: string) => void
  selectConversation: (id: string) => void
  updateConversationTitle: (id: string, title: string) => void
  clearConversations: () => void
  addMessage: (conversationId: string, message: Message) => void
  updateMessage: (conversationId: string, messageId: string, updates: Partial<Message>) => void
  deleteMessage: (conversationId: string, messageId: string) => void
}

export const useConversationStore = create<ConversationState>()(
  persist(
    (set, get) => ({
      conversations: [],
      currentConversationId: null,

      getCurrentConversation: () => {
        const { conversations, currentConversationId } = get()
        if (!currentConversationId) return null
        return conversations.find((c) => c.id === currentConversationId) || null
      },

      createConversation: (model?: string) => {
        const id = generateId()
        const newConversation: Conversation = {
          id,
          title: 'New Chat',
          messages: [],
          model: model || 'llama3.2:3b',
          createdAt: new Date(),
          updatedAt: new Date(),
        }
        set((state) => ({
          conversations: [newConversation, ...state.conversations],
          currentConversationId: id,
        }))
        return id
      },

      deleteConversation: (id: string) => {
        set((state) => {
          const filtered = state.conversations.filter((c) => c.id !== id)
          const isCurrentDeleted = state.currentConversationId === id
          return {
            conversations: filtered,
            currentConversationId: isCurrentDeleted
              ? filtered[0]?.id || null
              : state.currentConversationId,
          }
        })
      },

      selectConversation: (id: string) => {
        set({ currentConversationId: id })
      },

      updateConversationTitle: (id: string, title: string) => {
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, title, updatedAt: new Date() } : c
          ),
        }))
      },

      clearConversations: () => {
        set({ conversations: [], currentConversationId: null })
      },

      addMessage: (conversationId: string, message: Message) => {
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id === conversationId) {
              const updatedConv = {
                ...c,
                messages: [...c.messages, message],
                updatedAt: new Date(),
              }
              if (c.messages.length === 0 && message.role === 'user') {
                updatedConv.title =
                  message.content.slice(0, 50) +
                  (message.content.length > 50 ? '...' : '')
              }
              return updatedConv
            }
            return c
          }),
        }))
      },

      updateMessage: (
        conversationId: string,
        messageId: string,
        updates: Partial<Message>
      ) => {
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id === conversationId) {
              return {
                ...c,
                messages: c.messages.map((m) =>
                  m.id === messageId ? { ...m, ...updates } : m
                ),
                updatedAt: new Date(),
              }
            }
            return c
          }),
        }))
      },

      deleteMessage: (conversationId: string, messageId: string) => {
        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id === conversationId) {
              return {
                ...c,
                messages: c.messages.filter((m) => m.id !== messageId),
                updatedAt: new Date(),
              }
            }
            return c
          }),
        }))
      },
    }),
    {
      name: 'manic-ai-conversations',
      partialize: (state) => ({
        conversations: state.conversations,
        currentConversationId: state.currentConversationId,
      }),
    }
  )
)
