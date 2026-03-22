'use client'

import { useState, useRef, useEffect, useCallback, memo } from 'react'
import { RefreshIcon } from '@/components/ui/Icons'
import { useVirtualizer } from '@tanstack/react-virtual'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import ToolCallCard from './ToolCallCard'
import type { ToolCallData } from './ToolCallCard'
import type { Message, RagSource, ToolCallInfo } from '@/types'
import FeedbackButtons from './FeedbackButtons'

interface MessageListProps {
  messages: Message[]
  onRegenerate?: () => void
}

/** Estimated height per message for virtualizer */
const ESTIMATED_MESSAGE_HEIGHT = 150

export default function MessageList({ messages, onRegenerate }: MessageListProps) {
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

  return (
    <div
      ref={parentRef}
      className="h-full overflow-auto"
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
  )
}

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
  const isUser = message.role === 'user'
  const isAssistant = message.role === 'assistant'

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [message.content])

  return (
    <div
      className="px-4 py-6 animate-fade-in border-b border-[var(--border-color)]"
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
                components={{
                  code({ node, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '')
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

                    return (
                      <div className="relative group">
                        <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                          <CopyButton text={String(children).replace(/\n$/, '')} />
                        </div>
                        <SyntaxHighlighter
                          style={oneDark}
                          language={match?.[1] || 'text'}
                          PreTag="div"
                          customStyle={{
                            margin: 0,
                            borderRadius: '0.5rem',
                            fontSize: '0.875rem',
                            border: '1px solid var(--border-color)',
                          }}
                        >
                          {String(children).replace(/\n$/, '')}
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

          {/* Actions */}
          {isAssistant && !message.isStreaming && message.content && (
            <div className="flex items-center gap-2 mt-3">
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
              {onRegenerate && (
                <button
                  onClick={onRegenerate}
                  className="text-xs flex items-center gap-1 transition-colors hover:opacity-80"
                  style={{ color: 'var(--text-muted)' }}
                >
                  <RefreshIcon className="w-4 h-4" />
                  Regenerate
                </button>
              )}
              <FeedbackButtons
                messageId={message.id}
                responseText={message.content}
                hadRag={(message.sources?.length ?? 0) > 0}
              />
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
              key={source.id || idx}
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

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
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

