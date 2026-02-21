'use client'

import { useCallback, useRef } from 'react'
import { useChatStore } from '@/lib/store'
import { streamChat, generateMessageId } from '@/lib/api'
import type { Message, RagSource } from '@/types'

export function useChat() {
  const {
    currentConversation,
    currentConversationId,
    selectedModel,
    isGenerating,
    settings,
    useRag,
    createConversation,
    addMessage,
    updateMessage,
    setIsGenerating,
    setError,
  } = useChatStore()

  const abortControllerRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isGenerating) return

    let conversationId = currentConversationId
    if (!conversationId) {
      conversationId = createConversation()
    }

    const userMessage: Message = {
      id: generateMessageId(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    }
    addMessage(conversationId, userMessage)

    const assistantMessageId = generateMessageId()
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      model: selectedModel,
      isStreaming: true,
    }
    addMessage(conversationId, assistantMessage)

    setIsGenerating(true)
    setError(null)

    try {
      const state = useChatStore.getState()
      const conversation = state.conversations.find(c => c.id === conversationId)
      const messages = conversation?.messages
        .filter(m => m.role !== 'system' && m.id !== assistantMessageId)
        .map(m => ({ role: m.role, content: m.content })) || []

      let fullContent = ''
      let sources: RagSource[] = []

      for await (const event of streamChat({
        model: selectedModel,
        messages,
        temperature: settings.temperature,
        systemPrompt: settings.systemPrompt,
        useRag,
      })) {
        if (event.type === 'content' && event.content) {
          fullContent += event.content
          updateMessage(conversationId, assistantMessageId, {
            content: fullContent,
          })
        } else if (event.type === 'sources' && event.sources) {
          sources = event.sources
          updateMessage(conversationId, assistantMessageId, {
            sources,
          })
        } else if (event.type === 'error') {
          throw new Error(event.error || 'Stream error')
        }
      }

      updateMessage(conversationId, assistantMessageId, {
        content: fullContent,
        isStreaming: false,
        sources: sources.length > 0 ? sources : undefined,
      })
    } catch (error) {
      console.error('Chat error:', error)
      const errorMessage = error instanceof Error ? error.message : 'An error occurred'
      updateMessage(conversationId, assistantMessageId, {
        content: '',
        isStreaming: false,
        error: errorMessage,
      })
      setError(errorMessage)
    } finally {
      setIsGenerating(false)
    }
  }, [
    currentConversationId,
    selectedModel,
    isGenerating,
    settings,
    useRag,
    createConversation,
    addMessage,
    updateMessage,
    setIsGenerating,
    setError,
  ])

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsGenerating(false)
  }, [setIsGenerating])

  const regenerateLastMessage = useCallback(async () => {
    if (!currentConversation || currentConversation.messages.length < 2) return

    const messages = currentConversation.messages
    const lastUserMessageIndex = messages.findLastIndex(m => m.role === 'user')
    if (lastUserMessageIndex === -1) return

    const lastUserMessage = messages[lastUserMessageIndex]
    const lastAssistantMessage = messages[messages.length - 1]
    if (lastAssistantMessage.role === 'assistant') {
      useChatStore.getState().deleteMessage(currentConversation.id, lastAssistantMessage.id)
    }

    await sendMessage(lastUserMessage.content)
  }, [currentConversation, sendMessage])

  return {
    sendMessage,
    stopGeneration,
    regenerateLastMessage,
    isGenerating,
    currentConversation,
  }
}
