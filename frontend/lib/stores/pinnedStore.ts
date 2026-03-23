import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { Message } from '@/types'

export interface PinnedMessage {
  id: string
  role: Message['role']
  content: string
  /** Timestamp as ISO string for serialization safety */
  timestamp: string
  model?: string
}

interface PinnedState {
  pinnedMessages: PinnedMessage[]
  pinMessage: (message: Message) => void
  unpinMessage: (id: string) => void
  isPinned: (id: string) => boolean
}

export const usePinnedStore = create<PinnedState>()(
  persist(
    (set, get) => ({
      pinnedMessages: [],

      pinMessage: (message: Message) => {
        const already = get().pinnedMessages.some((p) => p.id === message.id)
        if (already) return
        const pinned: PinnedMessage = {
          id: message.id,
          role: message.role,
          content: message.content,
          timestamp: message.timestamp instanceof Date
            ? message.timestamp.toISOString()
            : String(message.timestamp),
          model: message.model,
        }
        set((state) => ({ pinnedMessages: [...state.pinnedMessages, pinned] }))
      },

      unpinMessage: (id: string) => {
        set((state) => ({
          pinnedMessages: state.pinnedMessages.filter((p) => p.id !== id),
        }))
      },

      isPinned: (id: string) => get().pinnedMessages.some((p) => p.id === id),
    }),
    {
      name: 'manic-ai-pinned',
      storage: createJSONStorage(() => localStorage),
    }
  )
)
