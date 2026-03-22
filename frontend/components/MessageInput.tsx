'use client'

import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { useChatStore } from '@/lib/store'
import { validateUploadedFile } from '@/lib/validation'

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
  const [attachedFile, setAttachedFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { useRag } = useChatStore()

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
      setAttachedFile(null)
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

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const result = validateUploadedFile(file)
    if (!result.valid) {
      setFileError(result.error ?? 'Invalid file')
      setTimeout(() => setFileError(null), 3000)
      e.target.value = ''
      return
    }
    setAttachedFile(file)
  }

  const removeAttachment = () => {
    setAttachedFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="relative max-w-3xl mx-auto">
      {/* Attached File Preview */}
      {attachedFile && (
        <div
          className="mb-2 px-3 py-2 rounded-lg flex items-center gap-2 text-sm animate-fade-in"
          style={{ background: 'var(--glass-bg)', border: '1px solid var(--border-color)' }}
        >
          <FileIcon className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--accent-blue)' }} />
          <span className="truncate flex-1" style={{ color: 'var(--text-secondary)' }}>
            {attachedFile.name}
          </span>
          <span className="text-xs flex-shrink-0" style={{ color: 'var(--text-muted)' }}>
            {formatSize(attachedFile.size)}
          </span>
          <button
            onClick={removeAttachment}
            className="p-0.5 rounded hover:opacity-80 flex-shrink-0"
            style={{ color: 'var(--text-muted)' }}
          >
            <CloseIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* File validation error */}
      {fileError && (
        <span className="block mb-1 text-xs" style={{ color: 'var(--status-error)' }}>
          {fileError}
        </span>
      )}

      {/* Input Area */}
      <div
        className="relative flex items-end gap-2 rounded-sm transition-all focus-within:border-cyan-500"
        style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
        }}
      >
        {/* Attachment Button */}
        {useRag && (
          <div className="flex items-center pl-2 pb-2.5">
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleFileSelect}
              accept=".txt,.md,.pdf,.csv,.json,.html,.xml,.py,.js,.ts,.java,.c,.cpp,.go,.rs,.rb"
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-1.5 rounded-lg transition-colors hover:opacity-80"
              style={{ color: 'var(--text-muted)' }}
              title="Attach file for RAG ingestion"
            >
              <PaperclipIcon className="w-5 h-5" />
            </button>
          </div>
        )}

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isGenerating}
          rows={1}
          className={`flex-1 py-4 bg-transparent resize-none focus:outline-none disabled:opacity-50 font-mono text-sm ${useRag ? 'pl-2' : 'pl-4'}`}
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

// Icons
function SendIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
    </svg>
  )
}

function StopIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 24 24">
      <rect x="6" y="6" width="12" height="12" rx="1" />
    </svg>
  )
}

function PaperclipIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
    </svg>
  )
}

function FileIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}
