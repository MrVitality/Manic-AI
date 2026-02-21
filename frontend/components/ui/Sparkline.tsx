'use client'

interface SparklineProps {
  values: number[]
  width?: number
  height?: number
  color?: string
  filled?: boolean
  className?: string
}

export default function Sparkline({
  values,
  width = 200,
  height = 32,
  color = 'var(--accent-blue)',
  filled = true,
  className = '',
}: SparklineProps) {
  if (values.length < 2) return null

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const padding = 2

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width
    const y = padding + (1 - (v - min) / range) * (height - padding * 2)
    return `${x},${y}`
  }).join(' ')

  const fillPoints = `0,${height} ${points} ${width},${height}`
  const id = `spark-${Math.random().toString(36).slice(2, 8)}`

  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className={`w-full ${className}`} style={{ height }}>
      <defs>
        <linearGradient id={`${id}-fill`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {filled && <polygon points={fillPoints} fill={`url(#${id}-fill)`} />}
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
