'use client'

import { useRef, useEffect, useState } from 'react'
import { ErrorIcon, CloseIcon } from '@/components/ui/Icons'
import { useChatStore, uiStoreApi } from '@/lib/store'
import { useArtifactStore } from '@/lib/stores/artifactStore'
import { useChat } from '@/hooks/useChat'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import ArtifactPanel from './ArtifactPanel'
import TokenCounter from './TokenCounter'
import ErrorBoundary from './ErrorBoundary'

export default function ChatArea() {
  const { currentConversation, error, useRag, setUseRag, useAgentMode, setUseAgentMode, selectedModel } = useChatStore()
  const { sendMessage, stopGeneration, regenerateLastMessage, isGenerating } = useChat()
  const isArtifactPanelOpen = useArtifactStore((s) => s.isArtifactPanelOpen)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [inputText, setInputText] = useState('')

  const handleSuggestionClick = (text: string) => {
    setInputText(text)
  }

  // Derive the currently-streaming assistant message content (if any)
  const streamingMessage = currentConversation?.messages.findLast(
    (m) => m.role === 'assistant' && m.isStreaming
  )
  const streamedText = streamingMessage?.content ?? ''

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [currentConversation?.messages])

  return (
    <div
      className={`flex-1 min-h-0 transition-all duration-300 ${isArtifactPanelOpen ? 'flex flex-col md:grid' : 'flex flex-col'}`}
      style={isArtifactPanelOpen ? { gridTemplateColumns: '60fr 40fr' } : undefined}
    >
      {/* Chat Column */}
      <ErrorBoundary sectionName="Chat">
        <div className="flex flex-col min-h-0 min-w-0 flex-1">
          {/* Mode Toggle Bar */}
          <div className="flex items-center justify-center gap-3 px-4 py-2 border-b border-[var(--border-color)] bg-[var(--bg-secondary)]">
            <button
              onClick={() => setUseRag(!useRag)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-sm text-xs font-mono tracking-wide transition-all uppercase border"
              style={useRag ? {
                borderColor: 'var(--accent-primary)',
                color: 'var(--accent-primary)',
                background: 'color-mix(in srgb, var(--accent-primary) 10%, transparent)',
              } : {
                borderColor: 'var(--border-color)',
                color: 'var(--text-muted)',
                background: 'transparent',
              }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              </svg>
              [RAG_MODE: {useRag ? 'ON' : 'OFF'}]
            </button>
            <button
              onClick={() => setUseAgentMode(!useAgentMode)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-sm text-xs font-mono tracking-wide transition-all uppercase border"
              style={useAgentMode ? {
                borderColor: 'var(--accent-cyan)',
                color: 'var(--accent-cyan)',
                background: 'color-mix(in srgb, var(--accent-cyan) 10%, transparent)',
              } : {
                borderColor: 'var(--border-color)',
                color: 'var(--text-muted)',
                background: 'transparent',
              }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2h-2" />
              </svg>
              [AGENT_MODE: {useAgentMode ? 'ON' : 'OFF'}]
            </button>
            {(useRag || useAgentMode) && (
              <span className="text-xs font-mono" style={{ color: useAgentMode ? 'var(--accent-cyan)' : 'var(--accent-primary)', opacity: 0.7 }}>
                {useAgentMode ? '// Agentic execution active' : '// Context injection active'}
              </span>
            )}
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto">
            {!currentConversation || currentConversation.messages.length === 0 ? (
              <EmptyState onSuggestionClick={handleSuggestionClick} />
            ) : (
              <MessageList messages={currentConversation.messages} onRegenerate={regenerateLastMessage} />
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Error Banner */}
          {error && (
            <div className="mx-4 mb-2 p-3 rounded-sm text-sm flex items-center gap-2 border border-red-500/30 bg-red-500/10 text-red-400 font-mono">
              <ErrorIcon className="w-5 h-5 flex-shrink-0" />
              <span>ERR: {error}</span>
              <button onClick={() => uiStoreApi.getState().setError(null)} className="ml-auto hover:text-red-300">
                <CloseIcon className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Input Area */}
          <div className="p-4 border-t border-[var(--border-color)] bg-[var(--bg-primary)]">
            <MessageInput
              onSend={(msg, attachments) => {
                let fullMessage = msg
                if (attachments && attachments.length > 0) {
                  const parts = attachments
                    .filter((a) => !a.isImage && a.text)
                    .map((a) => `\n\n[Attached file: ${a.name}]\n\`\`\`\n${a.text}\n\`\`\``)
                  if (parts.length > 0) fullMessage += parts.join('')
                }
                sendMessage(fullMessage)
                setInputText('')
              }}
              onStop={stopGeneration}
              isGenerating={isGenerating}
              inputText={inputText}
              onInputChange={setInputText}
            />
            <div className="max-w-3xl mx-auto mt-1">
              <TokenCounter
                inputText={inputText}
                isStreaming={isGenerating}
                streamedText={streamedText}
                model={selectedModel}
              />
            </div>
          </div>
        </div>
      </ErrorBoundary>

      {/* Artifact Panel (right pane, full-width below chat on mobile, side pane on md+) */}
      {isArtifactPanelOpen && (
        <div className="min-h-[300px] md:min-h-0">
          <ArtifactPanel />
        </div>
      )}
    </div>
  )
}

function EmptyState({ onSuggestionClick }: { onSuggestionClick: (text: string) => void }) {
  const suggestions = [
    { icon: '[?]', title: 'QUERY_CONCEPT', desc: 'Perform topic analysis', prompt: 'Explain the key concepts behind retrieval-augmented generation (RAG) and how it improves LLM accuracy.' },
    { icon: '[/]', title: 'EXECUTE_CODE', desc: 'Synthesize algorithms', prompt: 'Write a Python function that implements binary search with full type hints and docstring.' },
    { icon: '[T]', title: 'GEN_TEXT', desc: 'Output text stream', prompt: 'Write a concise technical summary of how transformer attention mechanisms work.' },
    { icon: '[#]', title: 'PARSE_DATA', desc: 'Process datasets', prompt: 'Given a CSV with columns: date, value, category — write a Python script to compute monthly averages per category.' },
  ]

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center font-mono">
      <div className="text-6xl mb-6 font-bold tracking-tighter" style={{ color: 'var(--accent-primary)' }}>
        &gt;_
      </div>
      <h2 className="text-2xl font-bold mb-2 uppercase tracking-widest" style={{ color: 'var(--accent-primary)' }}>System Ready</h2>
      <p className="max-w-md mb-8 text-sm" style={{ color: 'var(--text-muted)' }}>
        // Initialize sequence. Awaiting operator input parameter.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-lg w-full">
        {suggestions.map((s) => (
          <div
            key={s.title}
            role="button"
            tabIndex={0}
            className="p-4 rounded-sm cursor-pointer transition-all flex flex-col items-start text-left"
            style={{ border: '1px solid var(--border-color)', background: 'var(--glass-bg)' }}
            onClick={() => onSuggestionClick(s.prompt)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSuggestionClick(s.prompt) } }}
            onMouseEnter={(e) => {
              const el = e.currentTarget
              el.style.borderColor = 'var(--accent-primary)'
              el.style.background = 'color-mix(in srgb, var(--accent-primary) 5%, transparent)'
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget
              el.style.borderColor = 'var(--border-color)'
              el.style.background = 'var(--glass-bg)'
            }}
          >
            <span className="mb-2 font-bold" style={{ color: 'var(--accent-primary)' }}>{s.icon}</span>
            <h3 className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>{s.title}</h3>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{s.desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

