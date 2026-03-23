'use client'

import { useState, useRef, useEffect, useCallback, KeyboardEvent } from 'react'
import { useUiStore } from '@/lib/stores/uiStore'
import { validateUploadedFile } from '@/lib/validation'

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

// ---------------------------------------------------------------------------
// Slash command definitions
// ---------------------------------------------------------------------------

interface SlashCommand {
  name: string
  description: string
  /** The text to insert when the command is selected */
  insert: string
}

const SLASH_COMMANDS: SlashCommand[] = [
  { name: '/summarize', description: 'Summarize the conversation so far', insert: '/summarize' },
  { name: '/translate', description: 'Translate to another language', insert: '/translate ' },
  { name: '/model', description: 'Switch active model', insert: '/model ' },
  { name: '/clear', description: 'Clear the current chat', insert: '/clear' },
  { name: '/export', description: 'Export conversation as Markdown', insert: '/export' },
  { name: '/rag', description: 'Toggle RAG on or off', insert: '/rag ' },
  { name: '/agent', description: 'Toggle agent mode on or off', insert: '/agent ' },
  { name: '/focus', description: 'Toggle focus mode', insert: '/focus' },
]

// ---------------------------------------------------------------------------
// Smart paste content type detection
// ---------------------------------------------------------------------------

type PasteType = 'json' | 'url' | 'table' | null

function detectPasteType(text: string): PasteType {
  const trimmed = text.trim()
  // JSON: starts with { or [ and parses successfully
  if ((trimmed.startsWith('{') || trimmed.startsWith('[')) && trimmed.length > 2) {
    try {
      JSON.parse(trimmed)
      return 'json'
    } catch {
      // not valid JSON
    }
  }
  // URL: starts with http
  if (/^https?:\/\//i.test(trimmed)) {
    return 'url'
  }
  // Table: multi-line with tabs or pipe characters
  const lines = trimmed.split('\n')
  if (lines.length > 1) {
    const hasTabsOrPipes = lines.some((l) => l.includes('\t') || l.includes('|'))
    if (hasTabsOrPipes) return 'table'
  }
  return null
}

function formatAsCodeBlock(text: string): string {
  return '```json\n' + text.trim() + '\n```'
}

function formatAsTable(text: string): string {
  const lines = text.trim().split('\n').filter((l) => l.trim())
  const rows = lines.map((l) => l.split(/\t|\s{2,}|\|/).map((c) => c.trim()).filter(Boolean))
  if (rows.length === 0) return text
  const colCount = Math.max(...rows.map((r) => r.length))
  const pad = (s: string, n: number) => s.padEnd(n)
  const colWidths = Array.from({ length: colCount }, (_, ci) =>
    Math.max(...rows.map((r) => (r[ci] ?? '').length), 3)
  )
  const header = '| ' + rows[0].map((c, ci) => pad(c, colWidths[ci])).join(' | ') + ' |'
  const divider = '| ' + colWidths.map((w) => '-'.repeat(w)).join(' | ') + ' |'
  const body = rows.slice(1).map(
    (r) => '| ' + Array.from({ length: colCount }, (_, ci) => pad(r[ci] ?? '', colWidths[ci])).join(' | ') + ' |'
  )
  return [header, divider, ...body].join('\n')
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

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
  const setMessage = useCallback(
    (value: string) => {
      if (onInputChange) onInputChange(value)
      if (inputText === undefined) setInternalMessage(value)
    },
    [onInputChange, inputText]
  )

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([])
  const [isReadingFile, setIsReadingFile] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)

  // --- Slash command state ---
  const [showSlashMenu, setShowSlashMenu] = useState(false)
  const [slashFilter, setSlashFilter] = useState('')
  const [slashIndex, setSlashIndex] = useState(0)

  // --- Smart paste state ---
  const [pastePills, setPastePills] = useState<
    Array<{ id: string; label: string; type: PasteType; rawText: string }>
  >([])
  const pillDismissTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  // --- Focus mode action ---
  const toggleFocusMode = useUiStore((s) => s.toggleFocusMode)
  const setUseRag = useUiStore((s) => s.setUseRag)
  const setUseAgentMode = useUiStore((s) => s.setUseAgentMode)

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

  // Clear pill timers on unmount
  useEffect(() => {
    const timers = pillDismissTimers.current
    return () => {
      timers.forEach((t) => clearTimeout(t))
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Slash command helpers
  // ---------------------------------------------------------------------------

  const filteredCommands = SLASH_COMMANDS.filter((cmd) =>
    cmd.name.toLowerCase().includes(slashFilter.toLowerCase())
  )

  const dismissSlashMenu = useCallback(() => {
    setShowSlashMenu(false)
    setSlashFilter('')
    setSlashIndex(0)
  }, [])

  const selectSlashCommand = useCallback(
    (cmd: SlashCommand) => {
      // Execute built-in side effects for certain commands
      if (cmd.name === '/clear') {
        setMessage('')
        dismissSlashMenu()
        window.dispatchEvent(new CustomEvent('manic-clear-chat'))
        return
      }
      if (cmd.name === '/focus') {
        toggleFocusMode()
        setMessage('')
        dismissSlashMenu()
        return
      }
      // For all others, replace the partial slash text with the command insert text
      setMessage(cmd.insert)
      dismissSlashMenu()
      requestAnimationFrame(() => {
        const ta = textareaRef.current
        if (ta) {
          ta.focus()
          ta.setSelectionRange(ta.value.length, ta.value.length)
        }
      })
    },
    [setMessage, dismissSlashMenu, toggleFocusMode]
  )

  // ---------------------------------------------------------------------------
  // Smart paste helpers
  // ---------------------------------------------------------------------------

  const schedulePillDismiss = useCallback((id: string) => {
    const existing = pillDismissTimers.current.get(id)
    if (existing) clearTimeout(existing)
    const timer = setTimeout(() => {
      setPastePills((prev) => prev.filter((p) => p.id !== id))
      pillDismissTimers.current.delete(id)
    }, 5000)
    pillDismissTimers.current.set(id, timer)
  }, [])

  const dismissAllPills = useCallback(() => {
    pillDismissTimers.current.forEach((t) => clearTimeout(t))
    pillDismissTimers.current.clear()
    setPastePills([])
  }, [])

  const applyPill = useCallback(
    (id: string, type: PasteType, rawText: string) => {
      let transformed = rawText
      if (type === 'json') {
        transformed = formatAsCodeBlock(rawText)
      } else if (type === 'url') {
        transformed = `[Fetch & summarize]: ${rawText.trim()}`
      } else if (type === 'table') {
        transformed = formatAsTable(rawText)
      }
      // Replace the raw pasted text in the current message with the transformed version
      setMessage(message.replace(rawText, transformed))
      setPastePills((prev) => prev.filter((p) => p.id !== id))
      const existing = pillDismissTimers.current.get(id)
      if (existing) clearTimeout(existing)
      pillDismissTimers.current.delete(id)
    },
    [message, setMessage]
  )

  // ---------------------------------------------------------------------------
  // Event handlers
  // ---------------------------------------------------------------------------

  const handleSubmit = useCallback(() => {
    if (message.trim() && !isGenerating) {
      // Handle /rag on|off and /agent on|off before sending
      const ragMatch = message.trim().match(/^\/rag\s+(on|off)$/i)
      const agentMatch = message.trim().match(/^\/agent\s+(on|off)$/i)
      if (ragMatch) {
        setUseRag(ragMatch[1].toLowerCase() === 'on')
        setMessage('')
        return
      }
      if (agentMatch) {
        setUseAgentMode(agentMatch[1].toLowerCase() === 'on')
        setMessage('')
        return
      }
      onSend(message, attachedFiles.length > 0 ? attachedFiles : undefined)
      setMessage('')
      setAttachedFiles([])
      dismissAllPills()
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }
  }, [message, isGenerating, attachedFiles, onSend, setMessage, dismissAllPills, setUseRag, setUseAgentMode])

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value
      setMessage(value)

      // Dismiss pills on any keystroke
      if (pastePills.length > 0) dismissAllPills()

      // Slash command detection: open when first char is '/' and no space yet
      if (value === '/' || (value.startsWith('/') && !value.includes(' '))) {
        setSlashFilter(value.slice(1))
        setSlashIndex(0)
        setShowSlashMenu(true)
      } else {
        if (showSlashMenu) dismissSlashMenu()
      }
    },
    [setMessage, pastePills.length, dismissAllPills, showSlashMenu, dismissSlashMenu]
  )

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Slash menu navigation
      if (showSlashMenu) {
        if (e.key === 'ArrowDown') {
          e.preventDefault()
          setSlashIndex((i) => Math.min(i + 1, filteredCommands.length - 1))
          return
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault()
          setSlashIndex((i) => Math.max(i - 1, 0))
          return
        }
        if (e.key === 'Enter') {
          e.preventDefault()
          if (filteredCommands[slashIndex]) {
            selectSlashCommand(filteredCommands[slashIndex])
          }
          return
        }
        if (e.key === 'Escape') {
          e.preventDefault()
          dismissSlashMenu()
          return
        }
      }

      // Normal submit
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [showSlashMenu, slashIndex, filteredCommands, selectSlashCommand, dismissSlashMenu, handleSubmit]
  )

  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      const text = e.clipboardData.getData('text/plain')
      if (!text) return
      const type = detectPasteType(text)
      if (!type) return

      const id = `pill-${Date.now()}`
      const labelMap: Record<NonNullable<PasteType>, string> = {
        json: 'Format as code block',
        url: 'Fetch & summarize',
        table: 'Convert to table',
      }
      setPastePills((prev) => [...prev, { id, label: labelMap[type], type, rawText: text }])
      schedulePillDismiss(id)
    },
    [schedulePillDismiss]
  )

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    // Reset the input so the same file can be picked again
    e.target.value = ''

    // Validate file size and type before reading
    const isImage = IMAGE_MIME_TYPES.has(file.type)
    if (!isImage) {
      const validation = validateUploadedFile(file)
      if (!validation.valid) {
        setFileError(validation.error ?? 'Invalid file')
        setTimeout(() => setFileError(null), 5000)
        return
      }
    } else if (file.size > 10 * 1024 * 1024) {
      setFileError('Image too large (max 10 MB)')
      setTimeout(() => setFileError(null), 5000)
      return
    }
    setFileError(null)

    setIsReadingFile(true)
    try {

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

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="relative max-w-3xl mx-auto">
      {/* Slash command autocomplete panel */}
      {showSlashMenu && filteredCommands.length > 0 && (
        <div
          className="absolute bottom-full left-0 right-0 mb-2 rounded-sm overflow-hidden shadow-2xl z-50"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-color)',
            boxShadow: '0 -8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.04)',
          }}
          role="listbox"
          aria-label="Slash commands"
        >
          <div
            className="px-3 py-1.5 text-[10px] uppercase tracking-widest font-bold border-b"
            style={{ color: 'var(--text-muted)', borderColor: 'var(--border-color)' }}
          >
            Commands
          </div>
          {filteredCommands.map((cmd, idx) => {
            const isSelected = idx === slashIndex
            return (
              <button
                key={cmd.name}
                role="option"
                aria-selected={isSelected}
                onClick={() => selectSlashCommand(cmd)}
                onMouseEnter={() => setSlashIndex(idx)}
                className="w-full flex items-center gap-3 px-3 py-2 text-left transition-colors font-mono"
                style={{
                  background: isSelected
                    ? 'color-mix(in srgb, var(--accent-cyan) 10%, transparent)'
                    : 'transparent',
                  borderLeft: isSelected ? '2px solid var(--accent-cyan)' : '2px solid transparent',
                }}
              >
                <span
                  className="text-xs font-bold flex-shrink-0"
                  style={{ color: isSelected ? 'var(--accent-cyan)' : 'var(--text-secondary)' }}
                >
                  {cmd.name}
                </span>
                <span className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
                  {cmd.description}
                </span>
              </button>
            )
          })}
          <div
            className="flex items-center gap-3 px-3 py-1.5 text-[10px] border-t"
            style={{ borderColor: 'var(--border-color)', color: 'var(--text-muted)' }}
          >
            <span>
              <kbd className="px-1 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }}>↑↓</kbd>
              {' '}navigate
            </span>
            <span>
              <kbd className="px-1 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }}>↵</kbd>
              {' '}select
            </span>
            <span>
              <kbd className="px-1 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }}>Esc</kbd>
              {' '}dismiss
            </span>
          </div>
        </div>
      )}

      {/* Smart paste pills */}
      {pastePills.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {pastePills.map((pill) => (
            <button
              key={pill.id}
              onClick={() => applyPill(pill.id, pill.type, pill.rawText)}
              className="flex items-center gap-1.5 px-2 py-1 rounded-sm text-xs font-mono border transition-all hover:opacity-80"
              style={{
                borderColor: 'var(--accent-cyan)',
                background: 'color-mix(in srgb, var(--accent-cyan) 10%, transparent)',
                color: 'var(--accent-cyan)',
              }}
              title="Click to transform pasted content"
            >
              <WandIcon className="w-3 h-3 flex-shrink-0" />
              [{pill.label}]
            </button>
          ))}
        </div>
      )}

      {/* File validation error */}
      {fileError && (
        <div className="mb-2 px-3 py-1.5 rounded-sm text-xs font-mono" style={{ background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.35)', color: '#f87171' }}>
          {fileError}
        </div>
      )}

      {/* File Chips */}
      {attachedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {attachedFiles.map((file, index) => (
            <div
              key={`${file.name}-${index}`}
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
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={placeholder}
          disabled={isGenerating}
          rows={1}
          className="flex-1 py-4 pl-4 bg-transparent resize-none focus:outline-none disabled:opacity-50 font-mono text-sm"
          style={{ maxHeight: '200px', color: 'var(--text-primary)' }}
          aria-autocomplete={showSlashMenu ? 'list' : 'none'}
          aria-expanded={showSlashMenu}
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
        for new line &mdash; type{' '}
        <kbd className="px-1.5 py-0.5 rounded text-xs ml-1" style={{ background: 'var(--glass-bg)', color: 'var(--text-secondary)' }}>
          /
        </kbd>{' '}
        for commands
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

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function WandIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3l14 9-14 9V3z" />
    </svg>
  )
}
