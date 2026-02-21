'use client'

interface ScoreBarProps {
  label: string
  score: number
  maxScore?: number
  color?: string
  showValue?: boolean
  size?: 'sm' | 'md'
}

export default function ScoreBar({
  label,
  score,
  maxScore = 1,
  color,
  showValue = true,
  size = 'sm',
}: ScoreBarProps) {
  const pct = Math.min((score / maxScore) * 100, 100)
  const barColor = color || (pct > 70 ? '#10b981' : pct > 40 ? '#f59e0b' : '#ef4444')
  const h = size === 'sm' ? 'h-1.5' : 'h-2.5'

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs w-16 flex-shrink-0" style={{ color: 'var(--text-muted)' }}>
        {label}
      </span>
      <div className={`flex-1 ${h} rounded-full overflow-hidden`} style={{ background: 'var(--glass-bg)' }}>
        <div
          className={`${h} rounded-full transition-all duration-500 ease-out`}
          style={{ width: `${pct}%`, background: barColor }}
        />
      </div>
      {showValue && (
        <span className="text-xs font-mono w-12 text-right flex-shrink-0" style={{ color: 'var(--text-secondary)' }}>
          {score.toFixed(3)}
        </span>
      )}
    </div>
  )
}
