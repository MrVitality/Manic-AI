'use client'

import { useCallback, useEffect, useRef } from 'react'
import { useChatStore, conversationStoreApi } from '@/lib/store'
import { useArtifactStore } from '@/lib/stores/artifactStore'
import { streamChat, chat, generateMessageId } from '@/lib/api'
import type { Message, RagSource, ToolCallInfo } from '@/types'

export function useChat() {
  const {
    currentConversation,
    currentConversationId,
    selectedModel,
    isGenerating,
    settings,
    useRag,
    useAgentMode,
    createConversation,
    addMessage,
    updateMessage,
    setIsGenerating,
    setError,
  } = useChatStore()

  const abortControllerRef = useRef<AbortController | null>(null)

  // Cancel any in-flight stream when the component using this hook unmounts.
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort()
    }
  }, [])

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

    // Create a new AbortController for this stream so stopGeneration can cancel it
    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      const convState = conversationStoreApi.getState()
      const conversation = convState.conversations.find(c => c.id === conversationId)
      // Per-conversation system prompt overrides global settings prompt when set
      const effectiveSystemPrompt = conversation?.systemPrompt || settings.systemPrompt
      const isFirstExchange = (conversation?.messages.filter(m => m.role === 'user').length ?? 0) <= 1
      const shouldGenerateTitle = isFirstExchange && !conversation?.titleGenerated
      const firstUserMessage = content.trim()

      const messages = conversation?.messages
        .filter(m => m.role !== 'system' && m.id !== assistantMessageId)
        .map(m => ({ role: m.role, content: m.content })) || []

      let fullContent = ''
      let sources: RagSource[] = []
      let toolCalls: ToolCallInfo[] = []

      for await (const event of streamChat({
        model: selectedModel,
        messages,
        temperature: settings.temperature,
        systemPrompt: effectiveSystemPrompt,
        useRag,
      }, controller.signal, useAgentMode ? 'agent' : 'chat')) {
        if (event.type === 'content' && event.content) {
          fullContent += event.content
          updateMessage(conversationId, assistantMessageId, {
            content: fullContent,
          })

          // Detect artifact patterns in streamed content
          detectAndAddArtifacts(fullContent)
        } else if (event.type === 'sources' && event.sources) {
          sources = event.sources
          updateMessage(conversationId, assistantMessageId, {
            sources,
          })
        } else if (event.type === 'tool_start') {
          const toolCall: ToolCallInfo = {
            id: event.tool_call_id || `tc_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
            toolName: event.tool_name || 'tool',
            status: 'pending',
            description: event.tool_description || 'Searching knowledge base...',
            startedAt: Date.now(),
          }
          toolCalls = [...toolCalls, toolCall]
          updateMessage(conversationId, assistantMessageId, {
            toolCalls: [...toolCalls],
          })
        } else if (event.type === 'tool_end') {
          const callId = event.tool_call_id
          toolCalls = toolCalls.map((tc) =>
            tc.id === callId || (!callId && tc.status === 'pending')
              ? {
                  ...tc,
                  status: 'complete' as const,
                  description: event.tool_description || 'Search complete',
                  sources: event.sources,
                  completedAt: Date.now(),
                }
              : tc
          )
          updateMessage(conversationId, assistantMessageId, {
            toolCalls: [...toolCalls],
          })
        } else if (event.type === 'error') {
          // Mark any pending tool calls as errored
          toolCalls = toolCalls.map((tc) =>
            tc.status === 'pending'
              ? { ...tc, status: 'error' as const, error: event.error || 'Stream error', completedAt: Date.now() }
              : tc
          )
          throw new Error(event.error || 'Stream error')
        }
      }

      updateMessage(conversationId, assistantMessageId, {
        content: fullContent,
        isStreaming: false,
        sources: sources.length > 0 ? sources : undefined,
        toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
      })

      // Generate an AI title after the first assistant response completes
      if (shouldGenerateTitle && firstUserMessage) {
        conversationStoreApi.getState().markTitleGenerated(conversationId)
        generateConversationTitle(conversationId, firstUserMessage, selectedModel).catch(
          (err) => console.warn('[useChat] title generation failed:', err)
        )
      }
    } catch (error) {
      // If the user aborted, don't treat it as a real error
      if (controller.signal.aborted) {
        updateMessage(conversationId, assistantMessageId, {
          isStreaming: false,
        })
      } else {
        console.error('Chat error:', error)
        const errorMessage = error instanceof Error ? error.message : 'An error occurred'
        updateMessage(conversationId, assistantMessageId, {
          content: '',
          isStreaming: false,
          error: errorMessage,
        })
        setError(errorMessage)
      }
    } finally {
      abortControllerRef.current = null
      setIsGenerating(false)
    }
  }, [
    currentConversationId,
    selectedModel,
    isGenerating,
    settings,
    useRag,
    useAgentMode,
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
      conversationStoreApi.getState().deleteMessage(currentConversation.id, lastAssistantMessage.id)
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

// ---------------------------------------------------------------------------
// Artifact detection: parses completed fenced code blocks from streamed
// content and opens them in the artifact panel for large blocks (>6 lines).
// ---------------------------------------------------------------------------
const detectedBlockHashes = new Set<string>()

function detectAndAddArtifacts(content: string) {
  const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g
  let match: RegExpExecArray | null

  while ((match = codeBlockRegex.exec(content)) !== null) {
    const language = match[1] || 'text'
    const code = match[2].trim()

    // Only surface non-trivial blocks (>6 lines)
    if (code.split('\n').length <= 6) continue

    // Deduplicate using a simple hash of the first 200 chars
    const hash = `${language}:${code.slice(0, 200)}`
    if (detectedBlockHashes.has(hash)) continue
    detectedBlockHashes.add(hash)

    const isHtml = language === 'html' && code.includes('<')
    const isMarkdown = language === 'markdown' || language === 'md'

    useArtifactStore.getState().addArtifact({
      id: `art_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      type: isHtml ? 'html' : isMarkdown ? 'markdown' : 'code',
      title: `${language.toUpperCase()} snippet`,
      content: code,
      language: isHtml || isMarkdown ? undefined : language,
      createdAt: new Date(),
    })
  }
}

// ---------------------------------------------------------------------------
// AI title generation: calls the non-streaming chat endpoint to produce a
// concise 3-6 word title from the user's first message, then persists it.
// Fires after the first assistant response completes; errors are non-fatal.
// ---------------------------------------------------------------------------
async function generateConversationTitle(
  conversationId: string,
  firstUserMessage: string,
  model: string
): Promise<void> {
  const truncated = firstUserMessage.slice(0, 300)
  const result = await chat({
    model,
    messages: [
      {
        role: 'user',
        content: `Generate a concise 3-6 word title for this conversation. Reply with ONLY the title, no punctuation, no quotes: ${truncated}`,
      },
    ],
    temperature: 0.3,
  })

  const rawTitle = result.content.trim()
  if (rawTitle) {
    // Strip surrounding quotes/punctuation the model may add despite instructions
    const cleanTitle = rawTitle.replace(/^["']|["']$/g, '').trim()
    if (cleanTitle) {
      conversationStoreApi.getState().updateConversationTitle(conversationId, cleanTitle)
    }
  }
}
