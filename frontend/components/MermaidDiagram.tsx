'use client'

import { useEffect, useRef, useState } from 'react'
import DOMPurify from 'dompurify'

interface MermaidDiagramProps {
  code: string
  id: string
}

export default function MermaidDiagram({ code, id }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [rendered, setRendered] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function render() {
      try {
        const mermaid = (await import('mermaid')).default

        mermaid.initialize({
          startOnLoad: false,
          theme: 'dark',
          themeVariables: {
            background: 'transparent',
            primaryColor: '#818cf8',
            primaryTextColor: '#e2e8f0',
            primaryBorderColor: '#334155',
            lineColor: '#64748b',
            secondaryColor: '#1e293b',
            tertiaryColor: '#0f172a',
          },
          securityLevel: 'strict',
        })

        // mermaid.render requires a unique element ID each call to avoid collisions
        const diagramId = `mermaid-svg-${id}-${Date.now()}`
        const { svg } = await mermaid.render(diagramId, code)

        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = DOMPurify.sanitize(svg, { USE_PROFILES: { svg: true, svgFilters: true }, FORBID_TAGS: ['script'], FORBID_ATTR: ['onerror', 'onload', 'onclick'] })
          // Make the generated SVG responsive
          const svgEl = containerRef.current.querySelector('svg')
          if (svgEl) {
            svgEl.style.maxWidth = '100%'
            svgEl.style.height = 'auto'
          }
          setRendered(true)
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : 'Diagram render failed'
          setError(message)
        }
      }
    }

    render()

    return () => {
      cancelled = true
    }
  }, [code, id])

  if (error) {
    return (
      <div
        className="rounded p-3 my-2 border font-mono text-xs"
        style={{
          background: 'var(--bg-elevated)',
          borderColor: 'var(--border-color)',
          color: 'var(--text-muted)',
        }}
      >
        <div
          className="mb-2 text-[10px] uppercase tracking-widest font-bold"
          style={{ color: 'color-mix(in srgb, #f87171 70%, transparent)' }}
        >
          [MERMAID_RENDER_ERROR]
        </div>
        <pre className="whitespace-pre-wrap break-words" style={{ color: 'var(--text-secondary)' }}>
          {code}
        </pre>
        <div className="mt-2 text-[10px]" style={{ color: '#f87171' }}>
          {error}
        </div>
      </div>
    )
  }

  return (
    <div
      className="my-3 rounded border overflow-x-auto"
      style={{
        background: 'var(--bg-elevated)',
        borderColor: 'var(--border-color)',
        padding: '1rem',
        // Keep the container hidden until SVG is injected to avoid layout flicker
        minHeight: rendered ? undefined : '3rem',
      }}
    >
      {!rendered && (
        <div
          className="text-[10px] font-mono uppercase tracking-widest"
          style={{ color: 'var(--text-muted)' }}
        >
          [RENDERING_DIAGRAM...]
        </div>
      )}
      <div ref={containerRef} />
    </div>
  )
}
