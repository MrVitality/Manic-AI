'use client'

import { useRef, useEffect } from 'react'
import { useChatStore } from '@/lib/store'
import { useChat } from '@/hooks/useChat'
import MessageList from './MessageList'
import MessageInput from './MessageInput'

export default function ChatArea() {
  const { currentConversation, error, useRag, setUseRag } = useChatStore()
  const { sendMessage, stopGeneration, regenerateLastMessage, isGenerating } = useChat()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [currentConversation?.messages])

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* RAG Toggle Bar */}
      <div className="flex items-center justify-center gap-3 px-4 py-2 border-b border-[var(--border-color)] bg-[var(--bg-secondary)]">
        <button
          onClick={() => setUseRag(!useRag)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-sm text-xs font-mono tracking-wide transition-all uppercase border ${useRag ? 'border-cyan-400 text-cyan-400 bg-cyan-400/10' : 'border-gray-700 text-gray-400 bg-transparent hover:border-gray-500'
            }`}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
          </svg>
          [RAG_MODE: {useRag ? 'ON' : 'OFF'}]
        </button>
        {useRag && (
          <span className="text-xs font-mono text-cyan-500/70">
            // Context injection active
          </span>
        )}
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        {!currentConversation || currentConversation.messages.length === 0 ? (
          <EmptyState />
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
          <button onClick={() => useChatStore.getState().setError(null)} className="ml-auto hover:text-red-300">
            <CloseIcon className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Input Area */}
      <div className="p-4 border-t border-[var(--border-color)] bg-[var(--bg-primary)]">
        <MessageInput onSend={sendMessage} onStop={stopGeneration} isGenerating={isGenerating} />
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center font-mono">
      <div className="text-6xl text-cyan-400 mb-6 font-bold tracking-tighter">
        &gt;_
      </div>
      <h2 className="text-2xl font-bold mb-2 uppercase tracking-widest text-cyan-400">System Ready</h2>
      <p className="max-w-md mb-8 text-gray-400 text-sm">
        // Initialize sequence. Awaiting operator input parameter.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-lg w-full">
        {[
          { icon: '[?]', title: 'QUERY_CONCEPT', desc: 'Perform topic analysis' },
          { icon: '[/]', title: 'EXECUTE_CODE', desc: 'Synthesize algorithms' },
          { icon: '[T]', title: 'GEN_TEXT', desc: 'Output text stream' },
          { icon: '[#]', title: 'PARSE_DATA', desc: 'Process datasets' },
        ].map((s) => (
          <div key={s.title} className="p-4 rounded-sm cursor-pointer transition-all border border-gray-800 hover:border-cyan-400 bg-gray-900/50 hover:bg-cyan-400/5 flex flex-col items-start text-left">
            <span className="text-cyan-400 mb-2 font-bold">{s.icon}</span>
            <h3 className="font-bold text-sm text-gray-200">{s.title}</h3>
            <p className="text-xs text-gray-500 mt-1">{s.desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function BoltIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>) }
function ErrorIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>) }
function CloseIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>) }
