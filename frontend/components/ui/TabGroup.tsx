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
      className="relative flex gap-1 p-1 rounded-lg"
      style={{ background: 'var(--glass-bg)', border: '1px solid var(--glass-border)' }}
    >
      <div
        className="absolute top-1 bottom-1 rounded-md transition-all duration-300 ease-out"
        style={{
          left: indicator.left,
          width: indicator.width,
          background: 'linear-gradient(135deg, rgba(59,130,246,0.2), rgba(139,92,246,0.2))',
          border: '1px solid rgba(59,130,246,0.3)',
        }}
      />
      {tabs.map((tab) => (
        <button
          key={tab.key}
          data-tab={tab.key}
          onClick={() => onChange(tab.key)}
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
