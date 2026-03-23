'use client'

import { useState, useRef, useEffect, KeyboardEvent } from 'react'

interface AttachedFile {
  name: string
  /** Plain text content for text-based files */
  text?: string
  /** Base64-encoded data URI for images */
  base64?: string
  isImage: boolean
}

interface MessageInputProps {
  onSend: (message: string, attachments?: AttachedFile[]) => void
  onStop: () => void
  isGenerating: boolean
  placeholder?: string
  /** Controlled input value (optional). When provided, the parent owns the state. */
  inputText?: string
  /** Called whenever the textarea value changes (required when inputText is provided). */
  onInputChange?: (value: string) => void
}

const ACCEPTED_TYPES = '.txt,.md,.pdf,.html,.docx,.png,.jpg,.jpeg,.gif,.webp'
const IMAGE_MIME_TYPES = new Set(['image/png', 'image/jpeg', 'image/gif', 'image/webp'])

export default function MessageInput({
  onSend,
  onStop,
  isGenerating,
  placeholder = 'Type a message...',
  inputText,
  onInputChange,
}: MessageInputProps) {
  const [internalMessage, setInternalMessage] = useState('')
  // Use controlled value when the parent provides one, otherwise fall back to local state
  const message = inputText !== undefined ? inputText : internalMessage
  const setMessage = (value: string) => {
    if (onInputChange) onInputChange(value)
    if (inputText === undefined) setInternalMessage(value)
  }
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([])
  const [isReadingFile, setIsReadingFile] = useState(false)

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
      onSend(message, attachedFiles.length > 0 ? attachedFiles : undefined)
      setMessage('')
      setAttachedFiles([])
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

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    // Reset the input so the same file can be picked again
    e.target.value = ''

    setIsReadingFile(true)
    try {
      const isImage = IMAGE_MIME_TYPES.has(file.type)

      if (isImage) {
        const base64 = await readAsDataURL(file)
        setAttachedFiles((prev) => [...prev, { name: file.name, base64, isImage: true }])
      } else {
        const text = await readAsText(file)
        setAttachedFiles((prev) => [...prev, { name: file.name, text, isImage: false }])
      }
    } catch {
      // If reading fails, skip silently — do not block the user
    } finally {
      setIsReadingFile(false)
      textareaRef.current?.focus()
    }
  }

  const removeAttachment = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  return (
    <div className="relative max-w-3xl mx-auto">
      {/* File Chips */}
      {attachedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {attachedFiles.map((file, index) => (
            <div
              key={index}
              className="flex items-center gap-1.5 px-2 py-1 rounded-sm text-xs font-mono border"
              style={{
                borderColor: 'var(--accent-cyan)',
                background: 'color-mix(in srgb, var(--accent-cyan) 8%, transparent)',
                color: 'var(--accent-cyan)',
              }}
            >
              {file.isImage ? (
                <svg className="w-3 h-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              ) : (
                <svg className="w-3 h-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
              )}
              <span className="max-w-[160px] truncate">{file.name}</span>
              <button
                onClick={() => removeAttachment(index)}
                className="ml-0.5 hover:opacity-60 transition-opacity"
                title="Remove attachment"
                aria-label={`Remove ${file.name}`}
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input Area */}
      <div
        className="relative flex items-end gap-2 rounded-sm transition-all focus-within:border-cyan-500"
        style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
        }}
      >
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_TYPES}
          className="hidden"
          onChange={handleFileChange}
          aria-hidden="true"
          tabIndex={-1}
        />

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
          {/* Attachment button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isGenerating || isReadingFile}
            title="Attach file"
            aria-label="Attach file"
            className="p-2 rounded-sm transition-colors hover:opacity-80 disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ color: 'var(--text-muted)' }}
          >
            {isReadingFile ? (
              <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
            )}
          </button>

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
              className={`px-4 py-2 rounded-sm transition-all border text-xs font-mono font-bold uppercase ${message.trim() ? 'bg-cyan-500 text-black border-cyan-500 hover:bg-transparent hover:text-cyan-400 hover:shadow-[0_0_10px_rgba(0,240,255,0.3)]' : 'bg-transparent disabled:opacity-50 disabled:cursor-not-allowed'}`}
              style={!message.trim() ? { color: 'var(--text-muted)', borderColor: 'var(--border-color)' } : undefined}
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

// ---------------------------------------------------------------------------
// File reading helpers
// ---------------------------------------------------------------------------

function readAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error)
    reader.readAsText(file)
  })
}

function readAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}
