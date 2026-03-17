'use client'

import { useRef, useEffect, useState } from 'react'

interface Tab {
  key: string
  label: string
  icon?: React.ReactNode
}

interface TabGroupProps {
  tabs: Tab[]
  activeTab: string
  onChange: (key: string) => void
  size?: 'sm' | 'md'
}

export default function TabGroup({ tabs, activeTab, onChange, size = 'md' }: TabGroupProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [indicator, setIndicator] = useState({ left: 0, width: 0 })

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const activeEl = container.querySelector(`[data-tab="${activeTab}"]`) as HTMLElement
    if (activeEl) {
      setIndicator({
        left: activeEl.offsetLeft,
        width: activeEl.offsetWidth,
      })
    }
  }, [activeTab])

  const textSize = size === 'sm' ? 'text-xs' : 'text-sm'

  return (
    <div
      ref={containerRef}
      role="tablist"
      aria-label="Tab navigation"
      className="relative flex gap-1 p-1 rounded-lg"
      style={{ background: 'var(--glass-bg)', border: '1px solid var(--glass-border)' }}
    >
      <div
        className="absolute top-1 bottom-1 rounded-md transition-all duration-300 ease-out"
        aria-hidden="true"
        style={{
          left: indicator.left,
          width: indicator.width,
          background: 'rgba(129,140,248,0.12)',
          border: '1px solid rgba(129,140,248,0.25)',
        }}
      />
      {tabs.map((tab) => (
        <button
          key={tab.key}
          data-tab={tab.key}
          role="tab"
          aria-selected={activeTab === tab.key}
          aria-controls={`tabpanel-${tab.key}`}
          id={`tab-${tab.key}`}
          tabIndex={activeTab === tab.key ? 0 : -1}
          onClick={() => onChange(tab.key)}
          onKeyDown={(e) => {
            const keys = tabs.map(t => t.key)
            const currentIndex = keys.indexOf(tab.key)
            let nextIndex = -1
            if (e.key === 'ArrowRight') nextIndex = (currentIndex + 1) % keys.length
            else if (e.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + keys.length) % keys.length
            else if (e.key === 'Home') nextIndex = 0
            else if (e.key === 'End') nextIndex = keys.length - 1
            if (nextIndex >= 0) {
              e.preventDefault()
              onChange(keys[nextIndex])
              const container = containerRef.current
              const nextEl = container?.querySelector(`[data-tab="${keys[nextIndex]}"]`) as HTMLElement
              nextEl?.focus()
            }
          }}
          className={`relative z-10 flex items-center gap-1.5 px-3 py-1.5 rounded-md ${textSize} font-medium transition-colors duration-200`}
          style={{
            color: activeTab === tab.key ? 'var(--accent-blue)' : 'var(--text-muted)',
          }}
        >
          {tab.icon}
          {tab.label}
        </button>
      ))}
    </div>
  )
}
