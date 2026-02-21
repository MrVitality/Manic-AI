'use client'

type BadgeVariant = 'healthy' | 'degraded' | 'offline' | 'unknown' | 'processing' | 'completed' | 'failed' | 'info'

interface BadgeProps {
  variant: BadgeVariant
  children: React.ReactNode
  size?: 'sm' | 'md'
  pulse?: boolean
}

const variantStyles: Record<BadgeVariant, { bg: string; text: string; dot: string }> = {
  healthy: { bg: 'rgba(16,185,129,0.1)', text: '#10b981', dot: '#10b981' },
  completed: { bg: 'rgba(16,185,129,0.1)', text: '#10b981', dot: '#10b981' },
  degraded: { bg: 'rgba(245,158,11,0.1)', text: '#f59e0b', dot: '#f59e0b' },
  processing: { bg: 'rgba(59,130,246,0.1)', text: '#3b82f6', dot: '#3b82f6' },
  offline: { bg: 'rgba(239,68,68,0.1)', text: '#ef4444', dot: '#ef4444' },
  failed: { bg: 'rgba(239,68,68,0.1)', text: '#ef4444', dot: '#ef4444' },
  unknown: { bg: 'rgba(107,114,128,0.1)', text: '#6b7280', dot: '#6b7280' },
  info: { bg: 'rgba(59,130,246,0.1)', text: '#3b82f6', dot: '#3b82f6' },
}

export default function Badge({ variant, children, size = 'sm', pulse = false }: BadgeProps) {
  const styles = variantStyles[variant]
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm'

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full ${textSize} font-medium`}
      style={{ background: styles.bg, color: styles.text }}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${pulse ? 'animate-pulse' : ''}`}
        style={{ background: styles.dot }}
      />
      {children}
    </span>
  )
}
