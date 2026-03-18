'use client'

import { useState, useCallback, memo, useMemo } from 'react'
import { useArtifactStore } from '@/lib/stores/artifactStore'
import type { ArtifactType } from '@/lib/stores/artifactStore'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

export default function ArtifactPanel() {
  const {
    artifacts,
    activeArtifactId,
    isArtifactPanelOpen,
    setActiveArtifact,
    closePanel,
    removeArtifact,
  } = useArtifactStore()

  const activeArtifact = useMemo(
    () => artifacts.find((a) => a.id === activeArtifactId) ?? null,
    [artifacts, activeArtifactId],
  )

  if (!isArtifactPanelOpen || !activeArtifact) {
    return null
  }

  return (
    <div
      className="flex flex-col border-l border-[var(--border-color)] bg-[var(--bg-primary)] animate-slide-in-right"
      style={{
        width: '100%',
        minWidth: 0,
      }}
    >
      {/* Title Bar */}
      <div
        className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border-color)] bg-[var(--bg-secondary)] font-mono text-xs"
      >
        <ArtifactTypeIcon type={activeArtifact.type} />
        <span className="flex-1 truncate font-bold uppercase tracking-wider text-gray-200">
          {activeArtifact.title}
        </span>
        <span
          className="text-[10px] px-1.5 py-0.5 border border-gray-700 text-gray-500 uppercase"
        >
          {activeArtifact.type}
          {activeArtifact.language ? ` :: ${activeArtifact.language}` : ''}
        </span>

        {/* Artifact Tabs (when multiple) */}
        {artifacts.length > 1 && (
          <div className="flex items-center gap-1 mx-2">
            {artifacts.map((a) => (
              <button
                key={a.id}
                onClick={() => setActiveArtifact(a.id)}
                className="px-2 py-0.5 text-[10px] border transition-colors"
                style={{
                  borderColor:
                    a.id === activeArtifactId ? 'var(--accent-cyan)' : 'var(--border-color)',
                  color:
                    a.id === activeArtifactId ? 'var(--accent-cyan)' : 'var(--text-muted)',
                  background:
                    a.id === activeArtifactId ? 'rgba(34, 211, 238, 0.08)' : 'transparent',
                }}
              >
                {a.title.length > 12 ? `${a.title.slice(0, 12)}...` : a.title}
              </button>
            ))}
          </div>
        )}

        <button
          onClick={() => removeArtifact(activeArtifact.id)}
          className="p-1 text-gray-500 hover:text-red-400 transition-colors"
          title="Remove artifact"
        >
          <TrashIcon className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={closePanel}
          className="p-1 text-gray-500 hover:text-gray-300 transition-colors"
          title="Close panel"
        >
          <CloseIcon className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-auto min-h-0">
        <ArtifactContent artifact={activeArtifact} />
      </div>
    </div>
  )
}

const ArtifactContent = memo(function ArtifactContent({
  artifact,
}: {
  artifact: { type: ArtifactType; content: string; language?: string }
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(artifact.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [artifact.content])

  if (artifact.type === 'code') {
    return (
      <div className="relative group h-full">
        <div className="absolute right-3 top-3 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={handleCopy}
            className="px-2 py-1 text-[10px] font-mono border transition-colors"
            style={{
              background: 'var(--bg-elevated)',
              borderColor: 'var(--border-color)',
              color: copied ? 'var(--accent-cyan)' : 'var(--text-secondary)',
            }}
          >
            {copied ? '[COPIED]' : '[COPY]'}
          </button>
        </div>
        <SyntaxHighlighter
          style={oneDark}
          language={artifact.language || 'text'}
          PreTag="div"
          customStyle={{
            margin: 0,
            borderRadius: 0,
            fontSize: '0.8125rem',
            lineHeight: '1.6',
            height: '100%',
            background: 'var(--bg-primary)',
          }}
          showLineNumbers
          lineNumberStyle={{
            color: 'rgba(107, 114, 128, 0.4)',
            fontSize: '0.7rem',
            paddingRight: '1em',
            userSelect: 'none',
          }}
        >
          {artifact.content}
        </SyntaxHighlighter>
      </div>
    )
  }

  if (artifact.type === 'markdown') {
    return (
      <div className="p-4 prose-chat">
        <ReactMarkdown
          components={{
            code({ className, children, ...props }) {
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
              )
            },
          }}
        >
          {artifact.content}
        </ReactMarkdown>
      </div>
    )
  }

  if (artifact.type === 'html') {
    return (
      <iframe
        srcDoc={artifact.content}
        sandbox="allow-scripts"
        className="w-full h-full border-0"
        style={{ background: '#fff' }}
        title="HTML Artifact Preview"
      />
    )
  }

  return (
    <pre className="p-4 text-sm text-gray-400 whitespace-pre-wrap font-mono">
      {artifact.content}
    </pre>
  )
})

function ArtifactTypeIcon({ type }: { type: ArtifactType }) {
  const className = 'w-4 h-4'
  const style = { color: 'var(--accent-cyan)' }

  if (type === 'code') {
    return (
      <svg className={className} style={style} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
      </svg>
    )
  }
  if (type === 'markdown') {
    return (
      <svg className={className} style={style} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    )
  }
  // html
  return (
    <svg className={className} style={style} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
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

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  )
}
