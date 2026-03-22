'use client'

import { useMemo, useId } from 'react'

interface DataPoint {
  label?: string
  value: number
}

interface AreaChartProps {
  data: DataPoint[]
  width?: number
  height?: number
  color?: string
  showGrid?: boolean
  showLabels?: boolean
  className?: string
}

export default function AreaChart({
  data,
  width = 600,
  height = 200,
  color = 'var(--accent-blue)',
  showGrid = true,
  showLabels = false,
  className = '',
}: AreaChartProps) {
  const rawId = useId()
  const gradientId = `area-${rawId.replace(/:/g, '')}-fill`

  const chart = useMemo(() => {
    if (data.length < 2) return null

    const paddingLeft = showLabels ? 40 : 0
    const paddingBottom = showLabels ? 24 : 0
    const chartW = width - paddingLeft
    const chartH = height - paddingBottom

    const values = data.map((d) => d.value)
    const min = Math.min(...values) * 0.9
    const max = Math.max(...values) * 1.1 || 1
    const range = max - min

    const points = data.map((d, i) => {
      const x = paddingLeft + (i / (data.length - 1)) * chartW
      const y = chartH - ((d.value - min) / range) * chartH
      return { x, y }
    })

    let path = `M ${points[0].x} ${points[0].y}`
    for (let i = 1; i < points.length; i++) {
      const cp1x = points[i - 1].x + (points[i].x - points[i - 1].x) * 0.4
      const cp1y = points[i - 1].y
      const cp2x = points[i].x - (points[i].x - points[i - 1].x) * 0.4
      const cp2y = points[i].y
      path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${points[i].x} ${points[i].y}`
    }

    const areaPath = `${path} L ${points[points.length - 1].x} ${chartH} L ${paddingLeft} ${chartH} Z`

    const gridLines = showGrid
      ? Array.from({ length: 4 }, (_, i) => chartH * (i / 3))
      : []

    return { path, areaPath, gridLines, chartH, paddingLeft }
  }, [data, width, height, showLabels, showGrid])

  if (!chart) return null

  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className={`w-full ${className}`} style={{ height }}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {chart.gridLines.map((y, i) => (
        <line key={i} x1={chart.paddingLeft} y1={y} x2={width} y2={y} stroke="var(--border-color)" strokeDasharray="4 4" />
      ))}
      <path d={chart.areaPath} fill={`url(#${gradientId})`} />
      <path d={chart.path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}
