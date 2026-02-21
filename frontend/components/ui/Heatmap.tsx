'use client'

import { useState } from 'react'
import type { HeatmapCell } from '@/types'

interface HeatmapProps {
  cells: HeatmapCell[]
  columns: number
  rows: number
  rowLabels?: string[]
  colLabels?: string[]
  colorScale?: (value: number) => string
  className?: string
}

const defaultColorScale = (value: number): string => {
  if (value < 50) return '#8b5cf6'
  if (value < 200) return '#3b82f6'
  if (value < 500) return '#f59e0b'
  return '#ef4444'
}

export default function Heatmap({
  cells,
  columns,
  rows,
  rowLabels,
  colLabels,
  colorScale = defaultColorScale,
  className = '',
}: HeatmapProps) {
  const [hoveredCell, setHoveredCell] = useState<HeatmapCell | null>(null)

  const cellMap = new Map<string, HeatmapCell>()
  cells.forEach((c) => cellMap.set(`${c.x}-${c.y}`, c))

  return (
    <div className={`relative ${className}`}>
      {hoveredCell && (
        <div
          className="absolute z-10 px-2 py-1 rounded text-xs pointer-events-none"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-color)',
            color: 'var(--text-primary)',
            top: -28,
            left: '50%',
            transform: 'translateX(-50%)',
          }}
        >
          {hoveredCell.label || `${hoveredCell.value}ms`}
        </div>
      )}
      <div className="flex gap-1">
        {rowLabels && (
          <div className="flex flex-col gap-[2px] pr-2 justify-center">
            {rowLabels.map((label, i) => (
              <div key={i} className="h-4 flex items-center">
                <span className="text-[10px] truncate max-w-[60px]" style={{ color: 'var(--text-muted)' }}>
                  {label}
                </span>
              </div>
            ))}
          </div>
        )}
        <div
          className="grid gap-[2px]"
          style={{ gridTemplateColumns: `repeat(${columns}, 16px)` }}
        >
          {Array.from({ length: rows }, (_, row) =>
            Array.from({ length: columns }, (_, col) => {
              const cell = cellMap.get(`${col}-${row}`)
              const value = cell?.value ?? 0
              return (
                <div
                  key={`${col}-${row}`}
                  className="w-4 h-4 rounded-sm transition-all duration-150 cursor-default hover:scale-150 hover:z-10"
                  style={{
                    background: value > 0 ? colorScale(value) : 'var(--glass-bg)',
                    opacity: value > 0 ? 0.8 : 0.3,
                  }}
                  onMouseEnter={() => cell && setHoveredCell(cell)}
                  onMouseLeave={() => setHoveredCell(null)}
                />
              )
            })
          )}
        </div>
      </div>
      {colLabels && (
        <div className="flex gap-[2px] mt-1" style={{ marginLeft: rowLabels ? 72 : 0 }}>
          {colLabels.map((label, i) => (
            <div key={i} className="w-4 text-center">
              <span className="text-[8px]" style={{ color: 'var(--text-muted)' }}>
                {label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
