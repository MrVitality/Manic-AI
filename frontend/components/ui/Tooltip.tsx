'use client'

import { useState, useRef, ReactNode } from 'react'

interface TooltipProps {
  content: string
  children: ReactNode
  position?: 'top' | 'bottom'
}

export default function Tooltip({ content, children, position = 'top' }: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  return (
    <div
      ref={ref}
      className="relative inline-flex"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      {visible && (
        <div
          className="absolute z-50 px-2 py-1 rounded text-xs whitespace-nowrap pointer-events-none animate-fade-in"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-color)',
            color: 'var(--text-primary)',
            ...(position === 'top'
              ? { bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: 6 }
              : { top: '100%', left: '50%', transform: 'translateX(-50%)', marginTop: 6 }),
          }}
        >
          {content}
        </div>
      )}
    </div>
  )
}
