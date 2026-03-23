'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useConversationStore } from '@/lib/stores/conversationStore'
import { TerminalIcon, CloseIcon } from '@/components/ui/Icons'

interface SystemPromptEditorProps {
  conversationId: string
}

export default function SystemPromptEditor({ conversationId }: SystemPromptEditorProps) {
  const { conversations, updateConversationSystemPrompt } = useConversationStore()
  const conversation = conversations.find((c) => c.id === conversationId)
  const currentPrompt = conversation?.systemPrompt ?? ''

  const [isOpen, setIsOpen] = useState(false)
  const [draft, setDraft] = useState(currentPrompt)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  // Sync draft when conversation changes (e.g. switching conversations)
  useEffect(() => {
    setDraft(conversation?.systemPrompt ?? '')
  }, [conversationId, conversation?.systemPrompt])

  // Focus textarea when the overlay opens
  useEffect(() => {
    if (isOpen) {
      textareaRef.current?.focus()
      textareaRef.current?.select()
    }
  }, [isOpen])

  const handleOpen = () => {
    setDraft(conversation?.systemPrompt ?? '')
    setIsOpen(true)
  }

  const handleClose = useCallback(() => {
    setIsOpen(false)
  }, [])

  const handleSave = useCallback(() => {
    updateConversationSystemPrompt(conversationId, draft.trim())
    setIsOpen(false)
  }, [conversationId, draft, updateConversationSystemPrompt])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Escape') {
      handleClose()
    }
    // Ctrl+Enter or Cmd+Enter to save
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleSave()
    }
  }

  // Close when clicking outside the panel
  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === overlayRef.current) {
      handleSave()
    }
  }

  const hasPrompt = Boolean(currentPrompt)

  return (
    <>
      <button
        onClick={handleOpen}
        title={hasPrompt ? 'Edit system prompt' : 'Add system prompt'}
        aria-label={hasPrompt ? 'Edit conversation system prompt' : 'Add conversation system prompt'}
        className="flex items-center gap-1.5 px-2 py-1 rounded-md text-xs transition-colors"
        style={{
          background: hasPrompt ? 'rgba(129, 140, 248, 0.12)' : 'transparent',
          color: hasPrompt ? 'var(--accent-indigo)' : 'var(--text-muted)',
          border: hasPrompt ? '1px solid rgba(129, 140, 248, 0.3)' : '1px solid transparent',
        }}
      >
        <TerminalIcon className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">System Prompt</span>
        {hasPrompt && (
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: 'var(--accent-indigo)' }}
            aria-label="System prompt active"
          />
        )}
      </button>

      {isOpen && (
        <div
          ref={overlayRef}
          role="dialog"
          aria-modal="true"
          aria-label="Edit system prompt"
          className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4"
          style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }}
          onClick={handleOverlayClick}
        >
          <div
            className="w-full max-w-xl rounded-xl shadow-2xl flex flex-col"
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-color)',
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-4 py-3"
              style={{ borderBottom: '1px solid var(--border-color)' }}
            >
              <div className="flex items-center gap-2">
                <TerminalIcon className="w-4 h-4" style={{ color: 'var(--accent-indigo)' }} />
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  System Prompt
                </span>
              </div>
              <button
                onClick={handleClose}
                aria-label="Close system prompt editor"
                className="p-1 rounded-md transition-colors hover:bg-white/10"
                style={{ color: 'var(--text-muted)' }}
              >
                <CloseIcon className="w-4 h-4" />
              </button>
            </div>

            {/* Textarea */}
            <div className="p-4">
              <textarea
                ref={textareaRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Enter a system prompt for this conversation only. This overrides the global system prompt from settings.&#10;&#10;Example: You are a Python expert. Answer concisely with code examples."
                rows={7}
                className="w-full resize-none rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-indigo)]"
                style={{
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-primary)',
                  lineHeight: '1.6',
                }}
              />
              <p className="mt-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                Press Ctrl+Enter to save, Escape to cancel.
              </p>
            </div>

            {/* Footer actions */}
            <div
              className="flex items-center justify-between px-4 py-3 gap-3"
              style={{ borderTop: '1px solid var(--border-color)' }}
            >
              <button
                onClick={() => setDraft('')}
                className="text-xs px-3 py-1.5 rounded-md transition-colors"
                style={{ color: 'var(--text-muted)' }}
              >
                Clear
              </button>
              <div className="flex gap-2">
                <button onClick={handleClose} className="btn-secondary text-sm px-4 py-1.5">
                  Cancel
                </button>
                <button onClick={handleSave} className="btn-primary text-sm px-4 py-1.5">
                  Save
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
