'use client'

interface LoadingSkeletonProps {
  /** Number of skeleton rows to display */
  rows?: number
  /** Optional title text shown above the skeleton */
  title?: string
}

export default function LoadingSkeleton({ rows = 5, title }: LoadingSkeletonProps) {
  return (
    <div className="w-full h-full p-6 animate-fade-in">
      {title && (
        <div
          className="text-xs font-mono uppercase tracking-widest mb-6"
          style={{ color: 'var(--text-muted)' }}
        >
          {title}
        </div>
      )}
      <div className="space-y-4">
        {/* Header skeleton */}
        <div className="flex items-center gap-3 mb-6">
          <div
            className="h-8 w-48 rounded animate-pulse"
            style={{ background: 'var(--bg-elevated)' }}
          />
          <div
            className="h-6 w-24 rounded animate-pulse"
            style={{ background: 'var(--bg-elevated)', animationDelay: '150ms' }}
          />
        </div>

        {/* Card skeletons */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: Math.min(rows, 3) }).map((_, i) => (
            <div
              key={`card-${i}`}
              className="rounded-lg border p-4 space-y-3"
              style={{
                background: 'var(--bg-secondary)',
                borderColor: 'var(--border-color)',
              }}
            >
              <div
                className="h-4 w-3/4 rounded animate-pulse"
                style={{ background: 'var(--bg-elevated)', animationDelay: `${i * 100}ms` }}
              />
              <div
                className="h-3 w-1/2 rounded animate-pulse"
                style={{ background: 'var(--bg-elevated)', animationDelay: `${i * 100 + 50}ms` }}
              />
              <div
                className="h-16 w-full rounded animate-pulse"
                style={{ background: 'var(--bg-elevated)', animationDelay: `${i * 100 + 100}ms` }}
              />
            </div>
          ))}
        </div>

        {/* Row skeletons */}
        {Array.from({ length: Math.max(rows - 3, 2) }).map((_, i) => (
          <div
            key={`row-${i}`}
            className="flex items-center gap-4 p-3 rounded border"
            style={{
              background: 'var(--bg-secondary)',
              borderColor: 'var(--border-color)',
            }}
          >
            <div
              className="h-10 w-10 rounded animate-pulse flex-shrink-0"
              style={{ background: 'var(--bg-elevated)', animationDelay: `${i * 75}ms` }}
            />
            <div className="flex-1 space-y-2">
              <div
                className="h-3 rounded animate-pulse"
                style={{
                  background: 'var(--bg-elevated)',
                  width: `${60 + (i * 7) % 30}%`,
                  animationDelay: `${i * 75 + 25}ms`,
                }}
              />
              <div
                className="h-2 rounded animate-pulse"
                style={{
                  background: 'var(--bg-elevated)',
                  width: `${40 + (i * 11) % 20}%`,
                  animationDelay: `${i * 75 + 50}ms`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
