'use client'

import { useState, useRef, useEffect, useCallback, memo, forwardRef, useImperativeHandle } from 'react'
import { useSearchParams } from 'next/navigation'
import { RefreshIcon } from '@/components/ui/Icons'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useConversationStore } from '@/lib/stores/conversationStore'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import MermaidDiagram from './MermaidDiagram'
import ToolCallCard from './ToolCallCard'
import type { ToolCallData } from './ToolCallCard'
import type { Message, RagSource, ToolCallInfo } from '@/types'
import FeedbackButtons from './FeedbackButtons'
import PinnedDrawer from './PinnedDrawer'
import { usePinnedStore } from '@/lib/stores/pinnedStore'

interface MessageListProps {
  messages: Message[]
  onRegenerate?: () => void
}

export interface MessageListHandle {
  scrollToMessage: (id: string) => void
}

/** Estimated height per message for virtualizer */
const ESTIMATED_MESSAGE_HEIGHT = 150

const MessageList = forwardRef<MessageListHandle, MessageListProps>(function MessageList(
  { messages, onRegenerate },
  ref
) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ESTIMATED_MESSAGE_HEIGHT,
    overscan: 5,
  })

  // Auto-scroll to bottom when new messages arrive or content streams
  const lastMessage = messages[messages.length - 1]
  const shouldAutoScroll = lastMessage?.isStreaming || false

  useEffect(() => {
    if (shouldAutoScroll && messages.length > 0) {
      virtualizer.scrollToIndex(messages.length - 1, { align: 'end' })
    }
  }, [shouldAutoScroll, messages.length, lastMessage?.content?.length, virtualizer])

  // Expose scrollToMessage via ref
  useImperativeHandle(ref, () => ({
    scrollToMessage: (id: string) => {
      const idx = messages.findIndex((m) => m.id === id)
      if (idx !== -1) {
        virtualizer.scrollToIndex(idx, { align: 'start' })
        // After scroll, briefly highlight
        requestAnimationFrame(() => {
          const el = parentRef.current?.querySelector(`[data-message-id="${id}"]`)
          if (el) {
            el.classList.add('message-highlight')
            setTimeout(() => el.classList.remove('message-highlight'), 1500)
          }
        })
      }
    },
  }), [messages, virtualizer])

  const scrollToMessage = useCallback((id: string) => {
    const idx = messages.findIndex((m) => m.id === id)
    if (idx !== -1) {
      virtualizer.scrollToIndex(idx, { align: 'start' })
    }
  }, [messages, virtualizer])

  // Deep-link: read ?conv=CONV_ID&msg=MSG_INDEX on mount and scroll to the target message.
  // Uses a ref so it only fires once after the virtualizer has rendered items.
  const searchParams = useSearchParams()
  const deepLinkHandledRef = useRef(false)
  const selectConversation = useConversationStore((s) => s.selectConversation)

  useEffect(() => {
    if (deepLinkHandledRef.current) return
    const convParam = searchParams.get('conv')
    const msgParam = searchParams.get('msg')
    if (!convParam || msgParam === null) return

    // Switch to the referenced conversation if needed
    selectConversation(convParam)

    const msgIndex = parseInt(msgParam, 10)
    if (Number.isNaN(msgIndex) || msgIndex < 0) return

    // Wait one frame for the virtualizer to measure and render
    const raf = requestAnimationFrame(() => {
      virtualizer.scrollToIndex(msgIndex, { align: 'start' })
      deepLinkHandledRef.current = true
    })
    return () => cancelAnimationFrame(raf)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, messages.length])

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Pinned messages drawer sits at top of the message area */}
      <PinnedDrawer onScrollToMessage={scrollToMessage} />

      <div
        ref={parentRef}
        className="flex-1 overflow-auto"
        style={{ contain: 'strict' }}
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const message = messages[virtualRow.index]
            const isLast = virtualRow.index === messages.length - 1
            return (
              <div
                key={virtualRow.key}
                data-index={virtualRow.index}
                ref={virtualizer.measureElement}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <MemoizedMessageItem
                  message={message}
                  isLast={isLast}
                  onRegenerate={
                    message.role === 'assistant' && isLast ? onRegenerate : undefined
                  }
                />
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
})

export default MessageList

interface MessageItemProps {
  message: Message
  isLast: boolean
  onRegenerate?: () => void
}

const MemoizedMessageItem = memo<MessageItemProps>(function MessageItem({
  message,
  isLast,
  onRegenerate,
}) {
  const [copied, setCopied] = useState(false)
  const [linkCopied, setLinkCopied] = useState(false)
  const isUser = message.role === 'user'
  const isAssistant = message.role === 'assistant'
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const linkCopyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const { pinMessage, unpinMessage, isPinned } = usePinnedStore()
  const pinned = isPinned(message.id)

  useEffect(() => {
    return () => {
      if (copyTimerRef.current !== null) clearTimeout(copyTimerRef.current)
      if (linkCopyTimerRef.current !== null) clearTimeout(linkCopyTimerRef.current)
    }
  }, [])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.content)
    } catch {
      // Fallback for non-HTTPS or clipboard permission denied
      const textarea = document.createElement('textarea')
      textarea.value = message.content
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    setCopied(true)
    if (copyTimerRef.current !== null) clearTimeout(copyTimerRef.current)
    copyTimerRef.current = setTimeout(() => setCopied(false), 2000)
  }, [message.content])

  const handlePin = useCallback(() => {
    if (pinned) {
      unpinMessage(message.id)
    } else {
      pinMessage(message)
    }
  }, [pinned, message, pinMessage, unpinMessage])

  // Reads the message's index in the messages array from the DOM data-index attribute
  // on the virtualizer row, so we don't need to thread the index as a prop.
  const handleBookmark = useCallback(async () => {
    const convId = useConversationStore.getState().currentConversationId
    if (!convId) return

    const conversation = useConversationStore.getState().conversations.find((c) => c.id === convId)
    const msgIndex = conversation?.messages.findIndex((m) => m.id === message.id) ?? -1
    if (msgIndex === -1) return

    const url = `${window.location.origin}/chat?conv=${encodeURIComponent(convId)}&msg=${msgIndex}`

    try {
      await navigator.clipboard.writeText(url)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = url
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }

    setLinkCopied(true)
    if (linkCopyTimerRef.current !== null) clearTimeout(linkCopyTimerRef.current)
    linkCopyTimerRef.current = setTimeout(() => setLinkCopied(false), 2500)
  }, [message.id])

  return (
    <div
      data-message-id={message.id}
      className="px-4 py-6 animate-fade-in border-b border-[var(--border-color)] transition-colors duration-300"
      style={{
        background: isUser ? 'rgba(129, 140, 248, 0.03)' : 'transparent',
      }}
    >
      <div className="max-w-3xl mx-auto flex gap-4">
        {/* Avatar */}
        <div
          className="w-10 h-10 rounded-sm flex items-center justify-center flex-shrink-0 border font-mono font-bold text-xs"
          style={{
            background: isUser ? 'var(--bg-elevated)' : 'var(--accent-cyan)',
            borderColor: isUser ? 'var(--border-color)' : 'var(--accent-cyan)',
            color: isUser ? 'var(--text-secondary)' : '#000',
          }}
        >
          {isUser ? '[USR]' : '[SYS]'}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-2 font-mono uppercase tracking-widest text-xs">
            <span className="font-bold" style={{ color: isUser ? 'var(--text-secondary)' : 'var(--accent-cyan)' }}>
              {isUser ? '> OPERATOR_INPUT' : '> SYSTEM_RESPONSE'}
            </span>
            {message.model && (
              <span
                className="text-[10px] px-1.5 py-0.5 border"
                style={{ borderColor: 'var(--border-color)', color: 'var(--text-muted)', background: 'var(--bg-tertiary)' }}
              >
                {message.model}
              </span>
            )}
          </div>

          {/* Message Content */}
          {message.error ? (
            <div className="text-red-400 text-sm">
              Error: {message.error}
            </div>
          ) : message.isStreaming && !message.content ? (
            <div className="flex items-center gap-2" style={{ color: 'var(--text-muted)' }}>
              <LoadingDots />
              <span className="text-sm">Thinking...</span>
            </div>
          ) : (
            <div className="prose-chat">
              <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{
                  code({ node, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '')
                    const language = match?.[1] ?? ''
                    const codeText = String(children).replace(/\n$/, '')
                    const isInline = !match && !String(children).includes('\n')

                    if (isInline) {
                      return (
                        <code
                          className="px-1.5 py-0.5 rounded text-sm"
                          style={{ background: 'var(--bg-tertiary)' }}
                          {...props}
                        >
                          {children}
                        </code>
                      )
                    }

                    if (language === 'mermaid') {
                      // Derive a stable ID from the message id and a hash of the code
                      const diagramId = `${message.id}-${codeText.length}`
                      return <MermaidDiagram code={codeText} id={diagramId} />
                    }

                    return (
                      <div className="relative group">
                        <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                          <CopyButton text={codeText} />
                        </div>
                        <SyntaxHighlighter
                          style={oneDark}
                          language={language || 'text'}
                          PreTag="div"
                          customStyle={{
                            margin: 0,
                            borderRadius: '0.5rem',
                            fontSize: '0.875rem',
                            border: '1px solid var(--border-color)',
                          }}
                        >
                          {codeText}
                        </SyntaxHighlighter>
                      </div>
                    )
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
              {message.isStreaming && (
                <span className="typing-cursor">|</span>
              )}
            </div>
          )}

          {/* Tool Call Status Cards */}
          {isAssistant && message.toolCalls && message.toolCalls.length > 0 && (
            <div className="mt-3">
              {message.toolCalls.map((tc) => (
                <ToolCallCard
                  key={tc.id}
                  toolCall={{
                    id: tc.id,
                    toolName: tc.toolName,
                    status: tc.status,
                    description: tc.description,
                    sources: tc.sources,
                    error: tc.error,
                    startedAt: tc.startedAt,
                    completedAt: tc.completedAt,
                  }}
                />
              ))}
            </div>
          )}

          {/* Searching indicator when streaming with RAG but no tool calls yet */}
          {isAssistant && message.isStreaming && !message.content && !message.toolCalls?.length && (
            <div className="mt-2">
              <ToolCallCard
                toolCall={{
                  id: 'search-pending',
                  toolName: 'RAG_SEARCH',
                  status: 'pending',
                  description: 'Searching knowledge base...',
                  startedAt: Date.now(),
                }}
              />
            </div>
          )}

          {/* RAG Source Citations */}
          {isAssistant && !message.isStreaming && message.sources && message.sources.length > 0 && (
            <SourceCitations sources={message.sources} />
          )}

          {/* Actions — shown on all non-streaming messages that have content */}
          {!message.isStreaming && message.content && (
            <div className="flex items-center gap-2 mt-3">
              {/* Pin button — available on every message */}
              <button
                onClick={handlePin}
                className="text-xs flex items-center gap-1 transition-colors hover:opacity-80"
                style={{ color: pinned ? 'var(--accent-cyan)' : 'var(--text-muted)' }}
                title={pinned ? 'Unpin message' : 'Pin message'}
                aria-label={pinned ? 'Unpin message' : 'Pin message'}
              >
                <PinIcon className="w-4 h-4" filled={pinned} />
                {pinned ? 'Pinned' : 'Pin'}
              </button>

              {/* Bookmark / deep-link — available on every message */}
              <button
                onClick={handleBookmark}
                className="text-xs flex items-center gap-1 transition-colors hover:opacity-80"
                style={{ color: linkCopied ? 'var(--accent-emerald)' : 'var(--text-muted)' }}
                title="Copy link to this message"
                aria-label="Copy link to this message"
              >
                {linkCopied ? (
                  <>
                    <CheckIcon className="w-4 h-4" />
                    Link copied!
                  </>
                ) : (
                  <>
                    <BookmarkIcon className="w-4 h-4" />
                    Link
                  </>
                )}
              </button>

              {/* Copy — assistant messages only */}
              {isAssistant && (
                <button
                  onClick={handleCopy}
                  className="text-xs flex items-center gap-1 transition-colors hover:opacity-80"
                  style={{ color: 'var(--text-muted)' }}
                >
                  {copied ? (
                    <>
                      <CheckIcon className="w-4 h-4" />
                      Copied!
                    </>
                  ) : (
                    <>
                      <CopyIcon className="w-4 h-4" />
                      Copy
                    </>
                  )}
                </button>
              )}

              {/* Regenerate — assistant only, last message */}
              {isAssistant && onRegenerate && (
                <button
                  onClick={onRegenerate}
                  className="text-xs flex items-center gap-1 transition-colors hover:opacity-80"
                  style={{ color: 'var(--text-muted)' }}
                >
                  <RefreshIcon className="w-4 h-4" />
                  Regenerate
                </button>
              )}

              {isAssistant && (
                <FeedbackButtons
                  messageId={message.id}
                  responseText={message.content}
                  hadRag={(message.sources?.length ?? 0) > 0}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}, (prev, next) => {
  // Custom comparison: re-render only when message content or streaming state changes
  const toolCallsEqual =
    (prev.message.toolCalls?.length ?? 0) === (next.message.toolCalls?.length ?? 0) &&
    (prev.message.toolCalls ?? []).every((tc, i) => tc.status === next.message.toolCalls?.[i]?.status)

  return (
    prev.message.id === next.message.id &&
    prev.message.content === next.message.content &&
    prev.message.isStreaming === next.message.isStreaming &&
    prev.message.error === next.message.error &&
    toolCallsEqual &&
    prev.isLast === next.isLast &&
    prev.onRegenerate === next.onRegenerate
  )
})

// RAG Source Citations Component
const SourceCitations = memo(function SourceCitations({ sources }: { sources: RagSource[] }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="mt-4 font-mono">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs font-bold transition-opacity hover:opacity-80 uppercase tracking-widest"
        style={{ color: 'var(--accent-primary)' }}
      >
        <span style={{ color: 'var(--text-muted)' }}>[{expanded ? '-' : '+'}]</span>
        {sources.length} CONTEXT_SOURCES_INJECTED
      </button>

      {expanded && (
        <div className="mt-3 space-y-2 animate-fade-in">
          {sources.map((source, idx) => (
            <div
              key={source.id || `source-${idx}-${source.document_id}`}
              className="p-3 rounded-none text-sm border-l-2 border-y border-r"
              style={{
                borderColor: 'var(--border-color)',
                borderLeftColor: 'var(--accent-primary)',
                background: 'var(--bg-elevated)',
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold" style={{ color: 'var(--accent-primary)' }}>
                  SRC_{idx.toString().padStart(2, '0')}
                  {source.document_id && (
                    <span className="font-normal" style={{ color: 'var(--text-muted)' }}> :: {source.document_id.slice(0, 8)}</span>
                  )}
                </span>
                <div className="flex items-center gap-2">
                  <span
                    className="text-[10px] px-1 border"
                    style={{
                      borderColor: 'color-mix(in srgb, var(--accent-primary) 30%, transparent)',
                      color: 'var(--accent-primary)',
                      background: 'color-mix(in srgb, var(--accent-primary) 10%, transparent)',
                    }}
                  >
                    MATCH: {(source.score * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
              <p className="text-xs leading-relaxed line-clamp-3" style={{ color: 'var(--text-muted)' }}>
                {source.content}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
})

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (copyTimerRef.current !== null) clearTimeout(copyTimerRef.current)
    }
  }, [])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Clipboard unavailable — fail silently
      return
    }
    setCopied(true)
    if (copyTimerRef.current !== null) clearTimeout(copyTimerRef.current)
    copyTimerRef.current = setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className="p-1.5 rounded text-xs transition-colors"
      style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}
    >
      {copied ? 'Copied!' : 'Copy'}
    </button>
  )
}

function LoadingDots() {
  return (
    <div className="flex gap-1">
      <div className="w-2 h-2 rounded-full animate-pulse-slow" style={{ background: 'var(--text-muted)', animationDelay: '0ms' }} />
      <div className="w-2 h-2 rounded-full animate-pulse-slow" style={{ background: 'var(--text-muted)', animationDelay: '150ms' }} />
      <div className="w-2 h-2 rounded-full animate-pulse-slow" style={{ background: 'var(--text-muted)', animationDelay: '300ms' }} />
    </div>
  )
}

// Icons
function CopyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  )
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

function PinIcon({ className, filled }: { className?: string; filled?: boolean }) {
  return (
    <svg className={className} fill={filled ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
    </svg>
  )
}

function BookmarkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
      />
    </svg>
  )
}
