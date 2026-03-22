'use client'

interface PulseIndicatorProps {
  status: 'healthy' | 'degraded' | 'offline' | 'unknown'
  size?: 'sm' | 'md' | 'lg'
  ariaLabel?: string
}

const colors: Record<string, string> = {
  healthy: '#10b981',
  degraded: '#f59e0b',
  offline: '#ef4444',
  unknown: '#6b7280',
}

const sizes = { sm: 8, md: 12, lg: 16 }

export default function PulseIndicator({ status, size = 'md', ariaLabel }: PulseIndicatorProps) {
  const color = colors[status]
  const s = sizes[size]
  const isAlive = status === 'healthy' || status === 'degraded'

  return (
    <span className="relative inline-flex" role="status" aria-label={ariaLabel ?? status} style={{ width: s, height: s }}>
      {isAlive && (
        <span
          className="absolute inset-0 rounded-full animate-ping"
          style={{ background: color, opacity: 0.4, animationDuration: '2s' }}
        />
      )}
      <span
        className="relative inline-flex rounded-full w-full h-full"
        style={{
          background: color,
          boxShadow: `0 0 ${Math.floor(s * 0.5)}px ${color}40`,
        }}
      />
    </span>
  )
}
