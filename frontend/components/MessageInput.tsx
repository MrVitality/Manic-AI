'use client'

// TODO: File attachment support requires a multipart API endpoint.
// The file input UI has been removed until the backend supports it.
import { useState, useRef, useEffect, KeyboardEvent } from 'react'

interface MessageInputProps {
  onSend: (message: string) => void
  onStop: () => void
  isGenerating: boolean
  placeholder?: string
}

export default function MessageInput({
  onSend,
  onStop,
  isGenerating,
  placeholder = 'Type a message...',
}: MessageInputProps) {
  const [message, setMessage] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
    }
  }, [message])

  // Focus on mount
  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  const handleSubmit = () => {
    if (message.trim() && !isGenerating) {
      onSend(message)
      setMessage('')
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="relative max-w-3xl mx-auto">
      {/* Input Area */}
      <div
        className="relative flex items-end gap-2 rounded-sm transition-all focus-within:border-cyan-500"
        style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
        }}
      >
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isGenerating}
          rows={1}
          className="flex-1 py-4 pl-4 bg-transparent resize-none focus:outline-none disabled:opacity-50 font-mono text-sm"
          style={{ maxHeight: '200px', color: 'var(--text-primary)' }}
        />

        {/* Actions */}
        <div className="flex items-center gap-1 p-2">
          {isGenerating ? (
            <button
              onClick={onStop}
              className="px-4 py-2 bg-red-600/20 hover:bg-red-600/40 border border-red-500 text-red-500 rounded-sm transition-colors text-xs font-mono font-bold"
              title="Stop generating"
            >
              [STOP]
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!message.trim()}
              className={`px-4 py-2 rounded-sm transition-all border text-xs font-mono font-bold uppercase ${message.trim() ? 'bg-cyan-500 text-black border-cyan-500 hover:bg-transparent hover:text-cyan-400 hover:shadow-[0_0_10px_rgba(0,240,255,0.3)]' : 'bg-transparent text-gray-600 border-gray-800 disabled:opacity-50 disabled:cursor-not-allowed'}`}
              title="Send message (Enter)"
            >
              [EXEC]
            </button>
          )}
        </div>
      </div>

      {/* Helper text */}
      <div className="mt-2 text-xs text-center" style={{ color: 'var(--text-muted)' }}>
        Press{' '}
        <kbd className="px-1.5 py-0.5 rounded text-xs" style={{ background: 'var(--glass-bg)', color: 'var(--text-secondary)' }}>
          Enter
        </kbd>{' '}
        to send,{' '}
        <kbd className="px-1.5 py-0.5 rounded text-xs ml-1" style={{ background: 'var(--glass-bg)', color: 'var(--text-secondary)' }}>
          Shift + Enter
        </kbd>{' '}
        for new line
      </div>
    </div>
  )
}

