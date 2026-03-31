'use client'

import { useState, useCallback, memo, useMemo, useRef, useEffect } from 'react'
import { useArtifactStore } from '@/lib/stores/artifactStore'
import type { Artifact, ArtifactType } from '@/lib/stores/artifactStore'
import DOMPurify from 'dompurify'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

// ---------------------------------------------------------------------------
// Sandbox helpers
// ---------------------------------------------------------------------------

type SandboxableLanguage = 'javascript' | 'html' | 'python'

function isSandboxable(language: string | undefined): language is SandboxableLanguage {
  return language === 'javascript' || language === 'html' || language === 'python'
}

/** Build an srcdoc string for the sandboxed iframe. */
function buildSrcdoc(code: string, language: SandboxableLanguage): string {
  if (language === 'html') {
    return DOMPurify.sanitize(code, { ALLOW_UNKNOWN_PROTOCOLS: false })
  }
  // javascript: wrap in a minimal HTML shell that intercepts console output
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:ui-monospace,monospace;font-size:12px;background:#0d0d0d;color:#e5e7eb;padding:12px;line-height:1.6}
  .line{white-space:pre-wrap;word-break:break-all;padding:1px 0}
  .err{color:#f87171}.warn{color:#fbbf24}.info{color:#60a5fa}
</style>
</head>
<body>
<script>
(function(){
  function _emit(cls,args){
    var d=document.createElement('div');
    d.className='line'+cls;
    d.textContent=args.map(function(a){return typeof a==='object'?JSON.stringify(a,null,2):String(a);}).join(' ');
    document.body.appendChild(d);
  }
  var _log=console.log,_err=console.error,_warn=console.warn,_info=console.info;
  console.log  =function(){_emit(' ',Array.from(arguments));_log.apply(console,arguments);};
  console.error=function(){_emit(' err',Array.from(arguments));_err.apply(console,arguments);};
  console.warn =function(){_emit(' warn',Array.from(arguments));_warn.apply(console,arguments);};
  console.info =function(){_emit(' info',Array.from(arguments));_info.apply(console,arguments);};
  window.addEventListener('error',function(e){_emit(' err',[e.message]);});
})();
</script>
<script>
${code}
</script>
</body>
</html>`
}

// ---------------------------------------------------------------------------
// Compose Modal
// ---------------------------------------------------------------------------

function ComposeModal({
  artifacts,
  onClose,
}: {
  artifacts: Artifact[]
  onClose: () => void
}) {
  const [order, setOrder] = useState<string[]>(() => artifacts.map((a) => a.id))
  const dragIndexRef = useRef<number | null>(null)

  const orderedArtifacts = useMemo(
    () => order.map((id) => artifacts.find((a) => a.id === id)).filter(Boolean) as Artifact[],
    [order, artifacts]
  )

  const handleDragStart = (idx: number) => {
    dragIndexRef.current = idx
  }

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault()
    const from = dragIndexRef.current
    if (from === null || from === idx) return
    setOrder((prev) => {
      const next = [...prev]
      const [removed] = next.splice(from, 1)
      next.splice(idx, 0, removed)
      dragIndexRef.current = idx
      return next
    })
  }

  const handleDragEnd = () => {
    dragIndexRef.current = null
  }

  const exportAsMarkdown = () => {
    const sections = orderedArtifacts.map((a) => {
      const fence = a.type === 'code' ? `\`\`\`${a.language ?? ''}\n${a.content}\n\`\`\`` : a.content
      return `## ${a.title}\n\n${fence}`
    })
    const md = `# Composed Document\n\n${sections.join('\n\n---\n\n')}`
    triggerDownload(md, 'composed-document.md', 'text/markdown;charset=utf-8')
  }

  const exportAsPresentation = () => {
    const slides = orderedArtifacts
      .map((a) => {
        const body =
          a.type === 'code'
            ? `<pre><code class="language-${a.language ?? 'text'}">${escapeHtml(a.content)}</code></pre>`
            : a.type === 'html'
            ? a.content
            : `<p style="white-space:pre-wrap">${escapeHtml(a.content)}</p>`
        return `<section class="slide"><h2>${escapeHtml(a.title)}</h2><div class="body">${body}</div></section>`
      })
      .join('\n')

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Composed Presentation</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,sans-serif;background:#0f0f0f;color:#e5e5e5;display:flex;flex-direction:column;align-items:center;padding:2rem;gap:2rem}
  .slide{width:100%;max-width:900px;background:#1a1a1a;border:1px solid #2a2a2a;border-radius:12px;padding:2rem;page-break-after:always}
  .slide h2{font-size:1.5rem;margin-bottom:1rem;color:#a5b4fc;border-bottom:1px solid #2a2a2a;padding-bottom:.5rem}
  .body{font-size:.9rem;line-height:1.6;overflow:auto}
  pre{background:#111;border-radius:8px;padding:1rem;overflow:auto;font-size:.8rem}
  code{font-family:monospace}
  @media print{.slide{break-after:page}}
</style>
</head>
<body>${slides}</body>
</html>`
    triggerDownload(html, 'composed-presentation.html', 'text/html;charset=utf-8')
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="compose-modal-title"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="flex flex-col rounded-xl w-full max-w-lg mx-4"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-color)', maxHeight: '80vh' }}
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 font-mono text-xs" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <ComposeIcon className="w-4 h-4" style={{ color: 'var(--accent-cyan)' } as React.CSSProperties} />
          <span id="compose-modal-title" className="flex-1 font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
            Compose Artifacts
          </span>
          <button onClick={onClose} className="p-1 transition-colors" style={{ color: 'var(--text-muted)' }} aria-label="Close compose modal">
            <CloseIcon className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Instruction */}
        <p className="px-4 pt-3 pb-1 text-xs" style={{ color: 'var(--text-muted)' }}>
          Drag cards to reorder, then export.
        </p>

        {/* Draggable artifact list */}
        <div className="flex-1 overflow-y-auto px-4 py-2 space-y-2">
          {orderedArtifacts.map((a, idx) => (
            <div
              key={a.id}
              draggable
              onDragStart={() => handleDragStart(idx)}
              onDragOver={(e) => handleDragOver(e, idx)}
              onDragEnd={handleDragEnd}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-grab active:cursor-grabbing select-none"
              style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}
            >
              <DragHandleIcon className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--text-muted)' } as React.CSSProperties} />
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate font-medium" style={{ color: 'var(--text-primary)' }}>{a.title}</p>
                <p className="text-[10px] uppercase font-mono" style={{ color: 'var(--text-muted)' }}>
                  {a.type}{a.language ? ` :: ${a.language}` : ''}
                </p>
              </div>
              <span
                className="text-[9px] px-1.5 py-0.5 rounded font-mono"
                style={{ background: 'rgba(34,211,238,0.08)', color: 'var(--accent-cyan)', border: '1px solid rgba(34,211,238,0.2)' }}
              >
                #{idx + 1}
              </span>
            </div>
          ))}
          {orderedArtifacts.length === 0 && (
            <p className="text-center py-6 text-sm" style={{ color: 'var(--text-muted)' }}>No artifacts to compose.</p>
          )}
        </div>

        {/* Export buttons */}
        <div className="flex gap-2 px-4 py-3" style={{ borderTop: '1px solid var(--border-color)' }}>
          <button
            onClick={exportAsMarkdown}
            disabled={orderedArtifacts.length === 0}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-mono font-semibold rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: 'rgba(129,140,248,0.12)', color: 'var(--accent-indigo)', border: '1px solid rgba(129,140,248,0.3)' }}
          >
            <DocumentExportIcon className="w-3.5 h-3.5" />
            Export as Document
          </button>
          <button
            onClick={exportAsPresentation}
            disabled={orderedArtifacts.length === 0}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-mono font-semibold rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: 'rgba(34,211,238,0.10)', color: 'var(--accent-cyan)', border: '1px solid rgba(34,211,238,0.25)' }}
          >
            <PresentationIcon className="w-3.5 h-3.5" />
            Export as Presentation
          </button>
        </div>
      </div>
    </div>
  )
}

function triggerDownload(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// ---------------------------------------------------------------------------
// Main Panel
// ---------------------------------------------------------------------------

export default function ArtifactPanel() {
  const {
    artifacts,
    activeArtifactId,
    isArtifactPanelOpen,
    setActiveArtifact,
    closePanel,
    removeArtifact,
  } = useArtifactStore()

  const [isComposeOpen, setIsComposeOpen] = useState(false)

  const activeArtifact = useMemo(
    () => artifacts.find((a) => a.id === activeArtifactId) ?? null,
    [artifacts, activeArtifactId],
  )

  if (!isArtifactPanelOpen || !activeArtifact) {
    return null
  }

  return (
    <>
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
          <span className="flex-1 truncate font-bold uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
            {activeArtifact.title}
          </span>
          <span
            className="text-[10px] px-1.5 py-0.5 border uppercase"
            style={{ borderColor: 'var(--border-color)', color: 'var(--text-muted)' }}
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

          {/* COMPOSE button */}
          <button
            onClick={() => setIsComposeOpen(true)}
            className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono font-semibold border uppercase transition-colors"
            style={{
              borderColor: 'rgba(34,211,238,0.4)',
              color: 'var(--accent-cyan)',
              background: 'rgba(34,211,238,0.07)',
            }}
            title="Compose and export artifacts"
          >
            <ComposeIcon className="w-3 h-3" />
            [COMPOSE]
          </button>

          <button
            onClick={() => removeArtifact(activeArtifact.id)}
            className="p-1 hover:text-red-400 transition-colors"
            style={{ color: 'var(--text-muted)' }}
            title="Remove artifact"
          >
            <TrashIcon className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={closePanel}
            className="p-1 transition-colors"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-primary)' }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-muted)' }}
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

      {isComposeOpen && (
        <ComposeModal
          artifacts={artifacts}
          onClose={() => setIsComposeOpen(false)}
        />
      )}
    </>
  )
}

const ArtifactContent = memo(function ArtifactContent({
  artifact,
}: {
  artifact: { type: ArtifactType; content: string; language?: string }
}) {
  const [copied, setCopied] = useState(false)
  // sandbox state: null = not yet run, string = srcdoc to render
  const [sandboxSrc, setSandboxSrc] = useState<string | null>(null)
  // User must explicitly approve before executable code runs in the sandbox
  const [codeApproved, setCodeApproved] = useState(false)

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(artifact.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [artifact.content])

  const handleRun = useCallback(() => {
    // HTML artifact type: render srcDoc directly
    if (artifact.type === 'html') {
      setSandboxSrc(artifact.content)
      return
    }
    const lang = artifact.language as SandboxableLanguage | undefined
    if (!lang || !isSandboxable(lang)) return
    if (lang === 'python') {
      setSandboxSrc('__python__')
      return
    }
    setSandboxSrc(buildSrcdoc(artifact.content, lang))
  }, [artifact.content, artifact.language, artifact.type])

  const handleClearOutput = useCallback(() => {
    setSandboxSrc(null)
  }, [])

  // Reset approval whenever the artifact content changes
  useEffect(() => {
    setCodeApproved(false)
    setSandboxSrc(null)
  }, [artifact.content])

  if (artifact.type === 'code') {
    const canRun = isSandboxable(artifact.language)
    const isPython = artifact.language === 'python'

    return (
      <div className="flex flex-col h-full">
        {/* Execution approval warning banner */}
        {canRun && !isPython && !codeApproved && (
          <div
            className="flex items-center gap-2 px-3 py-2 text-xs font-mono"
            style={{ background: 'rgba(234,179,8,0.10)', borderBottom: '1px solid rgba(234,179,8,0.35)', color: '#ca8a04' }}
          >
            <span className="flex-1">This artifact contains executable code from the AI.</span>
            <button
              onClick={() => { setCodeApproved(true); handleRun() }}
              className="px-2 py-0.5 border font-semibold uppercase transition-colors"
              style={{ borderColor: 'rgba(234,179,8,0.6)', color: '#ca8a04', background: 'rgba(234,179,8,0.12)' }}
            >
              Run
            </button>
          </div>
        )}

        {/* Code toolbar */}
        <div
          className="flex items-center gap-1.5 px-3 py-1.5 border-b"
          style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
        >
          <button
            onClick={handleCopy}
            className="px-2 py-0.5 text-[10px] font-mono border transition-colors"
            style={{
              background: 'var(--bg-elevated)',
              borderColor: 'var(--border-color)',
              color: copied ? 'var(--accent-cyan)' : 'var(--text-secondary)',
            }}
          >
            {copied ? '[COPIED]' : '[COPY]'}
          </button>

          {canRun && (
            <>
              {codeApproved && (
                <button
                  onClick={handleRun}
                  className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono border uppercase font-semibold transition-colors"
                  style={{
                    background: 'rgba(16,185,129,0.08)',
                    borderColor: 'rgba(16,185,129,0.35)',
                    color: 'var(--accent-emerald)',
                  }}
                  title={isPython ? 'Python execution requires backend' : 'Run in sandbox'}
                >
                  <PlayIcon className="w-3 h-3" />
                  [RUN]
                </button>
              )}

              {sandboxSrc !== null && (
                <button
                  onClick={handleClearOutput}
                  className="px-2 py-0.5 text-[10px] font-mono border uppercase transition-colors"
                  style={{
                    background: 'var(--bg-elevated)',
                    borderColor: 'var(--border-color)',
                    color: 'var(--text-muted)',
                  }}
                >
                  [CLEAR]
                </button>
              )}
            </>
          )}
        </div>

        {/* Code + output split view */}
        <div className={`flex flex-col min-h-0 ${sandboxSrc !== null ? 'flex-1' : 'flex-1'}`}>
          {/* Code pane — shrinks when output is visible */}
          <div className={sandboxSrc !== null ? 'flex-shrink-0 overflow-auto' : 'flex-1 overflow-auto'}>
            <SyntaxHighlighter
              style={oneDark}
              language={artifact.language || 'text'}
              PreTag="div"
              customStyle={{
                margin: 0,
                borderRadius: 0,
                fontSize: '0.8125rem',
                lineHeight: '1.6',
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

          {/* Output pane */}
          {sandboxSrc !== null && (
            <div
              className="flex flex-col flex-1 min-h-0"
              style={{ borderTop: '1px solid var(--border-color)' }}
            >
              <div
                className="flex items-center gap-2 px-3 py-1 font-mono text-[10px]"
                style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)' }}
              >
                <span style={{ color: 'var(--accent-emerald)' }}>OUTPUT</span>
                {sandboxSrc === '__python__' && (
                  <span style={{ color: 'var(--text-muted)' }}>
                    — Python execution requires backend endpoint
                  </span>
                )}
              </div>

              {sandboxSrc === '__python__' ? (
                <div
                  className="flex-1 flex items-center justify-center p-6 text-center"
                  style={{ background: 'var(--bg-primary)' }}
                >
                  <div>
                    <PythonIcon className="w-8 h-8 mx-auto mb-3" style={{ color: 'var(--text-muted)' }} />
                    <p className="text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
                      Python execution requires backend endpoint
                    </p>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      A /api/execute/python endpoint is needed to run Python code securely.
                    </p>
                  </div>
                </div>
              ) : (
                <iframe
                  key={sandboxSrc}
                  srcDoc={sandboxSrc}
                  sandbox="allow-scripts"
                  className="flex-1 w-full border-0"
                  style={{ minHeight: '200px', background: '#0d0d0d' }}
                  title="Code execution output"
                />
              )}
            </div>
          )}
        </div>
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
      <div className="flex flex-col h-full">
        {/* Execution approval warning banner */}
        {!codeApproved && (
          <div
            className="flex items-center gap-2 px-3 py-2 text-xs font-mono"
            style={{ background: 'rgba(234,179,8,0.10)', borderBottom: '1px solid rgba(234,179,8,0.35)', color: '#ca8a04' }}
          >
            <span className="flex-1">This artifact contains executable code from the AI.</span>
            <button
              onClick={() => { setCodeApproved(true); handleRun() }}
              className="px-2 py-0.5 border font-semibold uppercase transition-colors"
              style={{ borderColor: 'rgba(234,179,8,0.6)', color: '#ca8a04', background: 'rgba(234,179,8,0.12)' }}
            >
              Run
            </button>
          </div>
        )}

        {/* HTML preview toolbar */}
        <div
          className="flex items-center gap-1.5 px-3 py-1.5 border-b"
          style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
        >
          {codeApproved && (
            <button
              onClick={handleRun}
              className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono border uppercase font-semibold transition-colors"
              style={{
                background: 'rgba(16,185,129,0.08)',
                borderColor: 'rgba(16,185,129,0.35)',
                color: 'var(--accent-emerald)',
              }}
              title="Reload preview"
            >
              <PlayIcon className="w-3 h-3" />
              [RUN]
            </button>
          )}
          {sandboxSrc !== null && (
            <button
              onClick={handleClearOutput}
              className="px-2 py-0.5 text-[10px] font-mono border uppercase transition-colors"
              style={{
                background: 'var(--bg-elevated)',
                borderColor: 'var(--border-color)',
                color: 'var(--text-muted)',
              }}
            >
              [CLEAR OUTPUT]
            </button>
          )}
        </div>

        {sandboxSrc !== null && (
          <div className="flex flex-col flex-1 min-h-0">
            <div
              className="flex-shrink-0 overflow-auto"
              style={{ maxHeight: '45%' }}
            >
              <SyntaxHighlighter
                style={oneDark}
                language="html"
                PreTag="div"
                customStyle={{
                  margin: 0,
                  borderRadius: 0,
                  fontSize: '0.8125rem',
                  lineHeight: '1.6',
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
            <div style={{ borderTop: '1px solid var(--border-color)' }} className="flex flex-col flex-1 min-h-0">
              <div
                className="px-3 py-1 font-mono text-[10px]"
                style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)' }}
              >
                <span style={{ color: 'var(--accent-emerald)' }}>PREVIEW</span>
              </div>
              <iframe
                key={sandboxSrc}
                srcDoc={sandboxSrc}
                sandbox="allow-scripts"
                className="flex-1 w-full border-0"
                style={{ background: '#fff' }}
                title="HTML Artifact Preview"
              />
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <pre className="p-4 text-sm whitespace-pre-wrap font-mono" style={{ color: 'var(--text-secondary)' }}>
      {artifact.content}
    </pre>
  )
})

function PlayIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="currentColor" viewBox="0 0 24 24">
      <path d="M8 5v14l11-7L8 5z" />
    </svg>
  )
}

function PythonIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 2C9.239 2 7 4.239 7 7v2h5v1H6a2 2 0 00-2 2v4c0 2.761 2.239 5 5 5h2c2.761 0 5-2.239 5-5v-2h-5v-1h6a2 2 0 002-2V7c0-2.761-2.239-5-5-5h-2zm-1 3.5a1 1 0 110 2 1 1 0 010-2zm2 11a1 1 0 110 2 1 1 0 010-2z" />
    </svg>
  )
}

function ComposeIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>
  )
}

function DragHandleIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="currentColor" viewBox="0 0 24 24">
      <path d="M8 6a1.5 1.5 0 110-3 1.5 1.5 0 010 3zM8 13.5a1.5 1.5 0 110-3 1.5 1.5 0 010 3zM8 21a1.5 1.5 0 110-3 1.5 1.5 0 010 3zM16 6a1.5 1.5 0 110-3 1.5 1.5 0 010 3zM16 13.5a1.5 1.5 0 110-3 1.5 1.5 0 010 3zM16 21a1.5 1.5 0 110-3 1.5 1.5 0 010 3z" />
    </svg>
  )
}

function DocumentExportIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )
}

function PresentationIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  )
}

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
