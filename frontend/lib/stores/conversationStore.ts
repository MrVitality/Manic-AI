import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { Conversation, Message } from '@/types'
import { getApiUrl } from '@/lib/api'

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
  markTitleGenerated: (id: string) => void
  updateConversationSystemPrompt: (id: string, systemPrompt: string) => void
  clearConversations: () => void
  exportAsMarkdown: (id: string) => void
  importConversation: (data: Record<string, unknown>) => void
  addMessage: (conversationId: string, message: Message) => void
  updateMessage: (conversationId: string, messageId: string, updates: Partial<Message>) => void
  deleteMessage: (conversationId: string, messageId: string) => void
  forkConversation: (conversationId: string, atMessageIndex: number) => string | null
  generateSummary: (id: string) => Promise<void>
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

      markTitleGenerated: (id: string) => {
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, titleGenerated: true } : c
          ),
        }))
      },

      updateConversationSystemPrompt: (id: string, systemPrompt: string) => {
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, systemPrompt, updatedAt: new Date() } : c
          ),
        }))
      },

      clearConversations: () => {
        set({ conversations: [], currentConversationId: null })
      },

      exportAsMarkdown: (id: string) => {
        const conversation = get().conversations.find((c) => c.id === id)
        if (!conversation) return

        const lines: string[] = [`# ${conversation.title}`, '']

        for (const message of conversation.messages) {
          const roleLabel =
            message.role === 'user'
              ? '## User'
              : message.role === 'assistant'
                ? '## Assistant'
                : '## System'
          lines.push(roleLabel, '', message.content, '', '---', '')
        }

        const markdown = lines.join('\n')
        const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${conversation.title.replace(/[^a-z0-9]/gi, '-').toLowerCase()}-${Date.now()}.md`
        a.click()
        URL.revokeObjectURL(url)
      },

      importConversation: (data: Record<string, unknown>) => {
        const validRoles = new Set(['user', 'assistant', 'system'])
        const validatedMessages: Message[] = Array.isArray(data.messages)
          ? (data.messages as Record<string, unknown>[])
              .filter(
                (m) =>
                  m &&
                  typeof m === 'object' &&
                  typeof m.role === 'string' &&
                  validRoles.has(m.role) &&
                  typeof m.content === 'string'
              )
              .map((m) => ({
                id: typeof m.id === 'string' ? m.id : generateId(),
                role: m.role as 'user' | 'assistant' | 'system',
                content: m.content as string,
                timestamp: typeof m.timestamp === 'string' ? new Date(m.timestamp) : new Date(),
              }))
          : []
        const conversation: Conversation = {
          id: generateId(),
          title: typeof data.title === 'string' && data.title.trim() ? data.title.trim() : 'Imported Conversation',
          messages: validatedMessages,
          model: typeof data.model === 'string' ? data.model : '',
          createdAt: data.createdAt ? new Date(data.createdAt as string) : new Date(),
          updatedAt: new Date(),
        }
        set((state) => ({
          conversations: [conversation, ...state.conversations],
          currentConversationId: conversation.id,
        }))
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

      forkConversation: (conversationId: string, atMessageIndex: number) => {
        const { conversations } = get()
        const parent = conversations.find((c) => c.id === conversationId)
        if (!parent) return null

        const forkedMessages = parent.messages
          .slice(0, atMessageIndex + 1)
          .map((m) => ({ ...m }))

        const newId = generateId()
        const branchLabel = `${parent.title} (branch)`
        const newConversation: Conversation = {
          id: newId,
          title: branchLabel,
          messages: forkedMessages,
          model: parent.model,
          createdAt: new Date(),
          updatedAt: new Date(),
          systemPrompt: parent.systemPrompt,
          parentId: conversationId,
        }

        set((state) => ({
          conversations: [
            newConversation,
            ...state.conversations.map((c) =>
              c.id === conversationId
                ? { ...c, branches: [...(c.branches ?? []), newId] }
                : c
            ),
          ],
          currentConversationId: newId,
        }))

        return newId
      },

      generateSummary: async (id: string) => {
        const { conversations } = get()
        const conversation = conversations.find((c) => c.id === id)
        if (!conversation || conversation.messages.length === 0) return

        // Build a condensed transcript for the summarization prompt
        const transcript = conversation.messages
          .filter((m) => m.role !== 'system')
          .map((m) => `${m.role === 'user' ? 'User' : 'Assistant'}: ${m.content.slice(0, 300)}`)
          .join('\n')

        const prompt =
          `Summarize the following conversation in 1-2 sentences. Be concise and focus on the main topic.\n\n${transcript}\n\nSummary:`

        try {
          const response = await fetch(`${getApiUrl()}/v1/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              model: conversation.model || 'llama3.2:3b',
              messages: [{ role: 'user', content: prompt }],
              stream: false,
            }),
          })

          if (!response.ok) return

          const data = await response.json() as {
            message?: { content?: string }
            data?: { message?: { content?: string } }
          }

          // Handle both direct and enveloped responses
          const summary =
            data?.message?.content ??
            data?.data?.message?.content ??
            null

          if (typeof summary === 'string' && summary.trim().length > 0) {
            set((state) => ({
              conversations: state.conversations.map((c) =>
                c.id === id ? { ...c, summary: summary.trim() } : c
              ),
            }))
          }
        } catch {
          // Silently fail — summary is optional
        }
      },
    }),
    {
      name: 'manic-ai-conversations',
      storage: createJSONStorage(() => localStorage),
      skipHydration: true,
      partialize: (state) => ({
        conversations: state.conversations,
        currentConversationId: state.currentConversationId,
      }),
    }
  )
)
