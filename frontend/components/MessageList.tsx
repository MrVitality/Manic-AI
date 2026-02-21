'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/cjs/styles/prism'
import type { Message, RagSource } from '@/types'

interface MessageListProps {
  messages: Message[]
  onRegenerate?: () => void
}

export default function MessageList({ messages, onRegenerate }: MessageListProps) {
  return (
    <div className="py-4">
      {messages.map((message, index) => (
        <MessageItem
          key={message.id}
          message={message}
          isLast={index === messages.length - 1}
          onRegenerate={message.role === 'assistant' && index === messages.length - 1 ? onRegenerate : undefined}
        />
      ))}
    </div>
  )
}

interface MessageItemProps {
  message: Message
  isLast: boolean
  onRegenerate?: () => void
}

function MessageItem({ message, isLast, onRegenerate }: MessageItemProps) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'
  const isAssistant = message.role === 'assistant'

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className="px-4 py-6 animate-fade-in border-b border-[var(--border-color)]"
      style={{
        background: isUser ? 'rgba(0, 240, 255, 0.02)' : 'transparent',
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
              <span className="text-[10px] px-1.5 py-0.5 border border-gray-700 text-gray-500 bg-gray-900/50">
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
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// RAG Source Citations Component
function SourceCitations({ sources }: { sources: RagSource[] }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="mt-4 font-mono">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs font-bold transition-colors hover:text-cyan-300 text-cyan-500 uppercase tracking-widest"
      >
        <span className="text-gray-500">[{expanded ? '-' : '+'}]</span>
        {sources.length} CONTEXT_SOURCES_INJECTED
      </button>

      {expanded && (
        <div className="mt-3 space-y-2 animate-fade-in">
          {sources.map((source, idx) => (
            <div
              key={source.id || idx}
              className="p-3 rounded-none text-sm border-l-2 border-y border-r border-y-[var(--border-color)] border-r-[var(--border-color)] border-l-cyan-500 bg-[var(--bg-elevated)]"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-cyan-400">
                  SRC_{idx.toString().padStart(2, '0')}
                  {source.document_id && (
                    <span className="text-gray-500 font-normal"> :: {source.document_id.slice(0, 8)}</span>
                  )}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] px-1 border border-cyan-500/30 text-cyan-500 bg-cyan-500/10">
                    MATCH: {(source.score * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
              <p className="text-xs leading-relaxed line-clamp-3 text-gray-400">
                {source.content}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

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
function UserIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  )
}

function BotIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  )
}

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

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  )
}

function SourceIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
    </svg>
  )
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  )
}
