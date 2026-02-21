'use client'

import { ReactNode } from 'react'

interface GlassPanelProps {
  children: ReactNode
  className?: string
  hover?: boolean
  glow?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const paddings = { none: '', sm: 'p-3', md: 'p-4', lg: 'p-6' }

export default function GlassPanel({ children, className = '', hover = false, glow = false, padding = 'md' }: GlassPanelProps) {
  return (
    <div
      className={`rounded-xl ${paddings[padding]} ${hover ? 'transition-all duration-300 hover:scale-[1.01]' : ''} ${glow ? 'animate-glow' : ''} ${className}`}
      style={{
        background: 'var(--glass-bg)',
        border: '1px solid var(--glass-border)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
      }}
    >
      {children}
    </div>
  )
}
