/**
 * Tests for the conversation Zustand store.
 *
 * Uses the store's static API (useConversationStore.getState / setState)
 * so we don't need renderHook for most operations.
 */
import { useConversationStore } from '@/lib/stores/conversationStore'
import type { Message } from '@/types'

// Reset store state before each test
beforeEach(() => {
  useConversationStore.setState({
    conversations: [],
    currentConversationId: null,
  })
})

describe('conversationStore', () => {
  describe('createConversation', () => {
    it('should create a new conversation and select it', () => {
      const id = useConversationStore.getState().createConversation('test-model')

      const state = useConversationStore.getState()
      expect(state.conversations).toHaveLength(1)
      expect(state.currentConversationId).toBe(id)
      expect(state.conversations[0].model).toBe('test-model')
      expect(state.conversations[0].title).toBe('New Chat')
      expect(state.conversations[0].messages).toEqual([])
    })

    it('should use default model when none specified', () => {
      useConversationStore.getState().createConversation()

      const conv = useConversationStore.getState().conversations[0]
      expect(conv.model).toBe('llama3.2:3b')
    })

    it('should prepend new conversations (newest first)', () => {
      useConversationStore.getState().createConversation('model-a')
      useConversationStore.getState().createConversation('model-b')

      const convs = useConversationStore.getState().conversations
      expect(convs[0].model).toBe('model-b')
      expect(convs[1].model).toBe('model-a')
    })
  })

  describe('deleteConversation', () => {
    it('should remove the conversation by id', () => {
      const id = useConversationStore.getState().createConversation()
      useConversationStore.getState().deleteConversation(id)

      expect(useConversationStore.getState().conversations).toHaveLength(0)
    })

    it('should select the next conversation when current is deleted', () => {
      const id1 = useConversationStore.getState().createConversation()
      const id2 = useConversationStore.getState().createConversation()

      // id2 is current (was created last)
      useConversationStore.getState().deleteConversation(id2)

      // Should fall back to id1
      expect(useConversationStore.getState().currentConversationId).toBe(id1)
    })

    it('should set currentConversationId to null when last conversation deleted', () => {
      const id = useConversationStore.getState().createConversation()
      useConversationStore.getState().deleteConversation(id)

      expect(useConversationStore.getState().currentConversationId).toBeNull()
    })
  })

  describe('selectConversation', () => {
    it('should update currentConversationId', () => {
      const id1 = useConversationStore.getState().createConversation()
      useConversationStore.getState().createConversation()

      useConversationStore.getState().selectConversation(id1)
      expect(useConversationStore.getState().currentConversationId).toBe(id1)
    })
  })

  describe('updateConversationTitle', () => {
    it('should update the title of the specified conversation', () => {
      const id = useConversationStore.getState().createConversation()
      useConversationStore.getState().updateConversationTitle(id, 'New Title')

      const conv = useConversationStore.getState().conversations.find((c) => c.id === id)
      expect(conv?.title).toBe('New Title')
    })
  })

  describe('clearConversations', () => {
    it('should remove all conversations', () => {
      useConversationStore.getState().createConversation()
      useConversationStore.getState().createConversation()
      useConversationStore.getState().clearConversations()

      const state = useConversationStore.getState()
      expect(state.conversations).toHaveLength(0)
      expect(state.currentConversationId).toBeNull()
    })
  })

  describe('addMessage', () => {
    it('should append a message to the conversation', () => {
      const id = useConversationStore.getState().createConversation()
      const msg: Message = {
        id: 'msg-1',
        role: 'user',
        content: 'Hello',
        timestamp: new Date(),
      }

      useConversationStore.getState().addMessage(id, msg)

      const conv = useConversationStore.getState().conversations.find((c) => c.id === id)
      expect(conv?.messages).toHaveLength(1)
      expect(conv?.messages[0].content).toBe('Hello')
    })

    it('should auto-title from first user message', () => {
      const id = useConversationStore.getState().createConversation()
      const msg: Message = {
        id: 'msg-1',
        role: 'user',
        content: 'What is machine learning?',
        timestamp: new Date(),
      }

      useConversationStore.getState().addMessage(id, msg)

      const conv = useConversationStore.getState().conversations.find((c) => c.id === id)
      expect(conv?.title).toBe('What is machine learning?')
    })
  })

  describe('updateMessage', () => {
    it('should update the specified message fields', () => {
      const id = useConversationStore.getState().createConversation()
      const msg: Message = {
        id: 'msg-1',
        role: 'assistant',
        content: 'Original',
        timestamp: new Date(),
      }
      useConversationStore.getState().addMessage(id, msg)

      useConversationStore.getState().updateMessage(id, 'msg-1', { content: 'Updated' })

      const conv = useConversationStore.getState().conversations.find((c) => c.id === id)
      expect(conv?.messages[0].content).toBe('Updated')
      expect(conv?.messages[0].role).toBe('assistant') // unchanged
    })
  })

  describe('deleteMessage', () => {
    it('should remove the specified message', () => {
      const id = useConversationStore.getState().createConversation()
      const msg: Message = {
        id: 'msg-1',
        role: 'user',
        content: 'Hello',
        timestamp: new Date(),
      }
      useConversationStore.getState().addMessage(id, msg)
      useConversationStore.getState().deleteMessage(id, 'msg-1')

      const conv = useConversationStore.getState().conversations.find((c) => c.id === id)
      expect(conv?.messages).toHaveLength(0)
    })
  })

  describe('getCurrentConversation', () => {
    it('should return null when no conversation is selected', () => {
      expect(useConversationStore.getState().getCurrentConversation()).toBeNull()
    })

    it('should return the current conversation', () => {
      const id = useConversationStore.getState().createConversation('my-model')
      const current = useConversationStore.getState().getCurrentConversation()

      expect(current).not.toBeNull()
      expect(current?.id).toBe(id)
      expect(current?.model).toBe('my-model')
    })
  })
})
