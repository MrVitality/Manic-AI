'use client'

interface BarData {
  label: string
  value: number
  maxValue?: number
  color?: string
}

interface BarChartProps {
  data: BarData[]
  direction?: 'horizontal' | 'vertical'
  showValues?: boolean
  className?: string
}

export default function BarChart({ data, direction = 'horizontal', showValues = true, className = '' }: BarChartProps) {
  const maxVal = Math.max(...data.map((d) => d.maxValue ?? d.value)) || 1

  if (direction === 'horizontal') {
    return (
      <div className={`space-y-3 ${className}`}>
        {data.map((item, i) => (
          <div key={i}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium truncate" style={{ color: 'var(--text-secondary)' }}>
                {item.label}
              </span>
              {showValues && (
                <span className="text-xs font-mono ml-2" style={{ color: 'var(--text-muted)' }}>
                  {item.value.toLocaleString()}
                </span>
              )}
            </div>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--glass-bg)' }}>
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{
                  width: `${(item.value / maxVal) * 100}%`,
                  background: item.color || 'linear-gradient(90deg, var(--accent-blue), var(--accent-purple))',
                }}
              />
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className={`flex items-end gap-2 ${className}`} style={{ height: 120 }}>
      {data.map((item, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1">
          <div className="w-full relative" style={{ height: 100 }}>
            <div
              className="absolute bottom-0 w-full rounded-t-md transition-all duration-700 ease-out"
              style={{
                height: `${(item.value / maxVal) * 100}%`,
                background: item.color || 'linear-gradient(180deg, var(--accent-blue), var(--accent-purple))',
                minHeight: 2,
              }}
            />
          </div>
          <span className="text-[10px] truncate max-w-full" style={{ color: 'var(--text-muted)' }}>
            {item.label}
          </span>
        </div>
      ))}
    </div>
  )
}
