'use client'

import { useEffect, useState } from 'react'
import type { DonutSegment } from '@/types'

interface DonutChartProps {
  segments: DonutSegment[]
  size?: number
  strokeWidth?: number
  centerLabel?: string
  centerValue?: string
  className?: string
}

export default function DonutChart({
  segments,
  size = 120,
  strokeWidth = 10,
  centerLabel,
  centerValue,
  className = '',
}: DonutChartProps) {
  const [animated, setAnimated] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setAnimated(true), 50)
    return () => clearTimeout(t)
  }, [])

  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1
  const center = size / 2

  let offset = 0

  return (
    <div className={`relative inline-flex items-center justify-center ${className}`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="var(--glass-border)"
          strokeWidth={strokeWidth}
        />
        {segments.map((segment, i) => {
          const pct = segment.value / total
          const dashLength = circumference * pct
          const dashOffset = circumference * (1 - offset / total)
          offset += segment.value

          return (
            <circle
              key={i}
              cx={center}
              cy={center}
              r={radius}
              fill="none"
              stroke={segment.color}
              strokeWidth={strokeWidth}
              strokeDasharray={`${dashLength} ${circumference - dashLength}`}
              strokeDashoffset={animated ? dashOffset : circumference}
              strokeLinecap="round"
              transform={`rotate(-90 ${center} ${center})`}
              style={{
                transition: 'stroke-dashoffset 1s ease-out',
                transitionDelay: `${i * 150}ms`,
              }}
            />
          )
        })}
      </svg>
      {(centerLabel || centerValue) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {centerValue && (
            <span className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
              {centerValue}
            </span>
          )}
          {centerLabel && (
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {centerLabel}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
