'use client'

import type { Settings } from '@/types'
import { useChatStore } from '@/lib/store'
import { useTheme } from '@/hooks/useTheme'
import GlassPanel from '@/components/ui/GlassPanel'

const ACCENT_COLORS: Array<{ id: string; label: string; color: string }> = [
  { id: 'indigo', label: 'Indigo', color: '#818cf8' },
  { id: 'violet', label: 'Violet', color: '#a78bfa' },
  { id: 'blue', label: 'Blue', color: '#3b82f6' },
  { id: 'purple', label: 'Purple', color: '#8b5cf6' },
  { id: 'emerald', label: 'Emerald', color: '#10b981' },
]

const FONT_SIZES: Array<{ id: string; label: string }> = [
  { id: 'sm', label: 'Small' },
  { id: 'base', label: 'Default' },
  { id: 'lg', label: 'Large' },
]

export default function AppearanceSettings() {
  const { settings, updateSettings } = useChatStore()
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Theme</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Choose light or dark mode</p>
        <GlassPanel className="p-4">
          <div className="flex gap-3">
            <button
              onClick={() => { if (theme !== 'dark') toggleTheme() }}
              className="flex-1 p-4 rounded-lg transition-all text-center"
              style={{
                background: theme === 'dark' ? 'rgba(129,140,248,0.1)' : 'var(--glass-bg)',
                border: `1px solid ${theme === 'dark' ? 'rgba(129,140,248,0.3)' : 'var(--glass-border)'}`,
              }}
            >
              <div className="w-8 h-8 mx-auto mb-2 rounded-lg" style={{ background: '#0a0a0f', border: '1px solid #333' }} />
              <span className="text-xs font-medium" style={{ color: theme === 'dark' ? 'var(--accent-blue)' : 'var(--text-secondary)' }}>Dark</span>
            </button>
            <button
              onClick={() => { if (theme !== 'light') toggleTheme() }}
              className="flex-1 p-4 rounded-lg transition-all text-center"
              style={{
                background: theme === 'light' ? 'rgba(129,140,248,0.1)' : 'var(--glass-bg)',
                border: `1px solid ${theme === 'light' ? 'rgba(129,140,248,0.3)' : 'var(--glass-border)'}`,
              }}
            >
              <div className="w-8 h-8 mx-auto mb-2 rounded-lg" style={{ background: '#f8f9fc', border: '1px solid #ddd' }} />
              <span className="text-xs font-medium" style={{ color: theme === 'light' ? 'var(--accent-blue)' : 'var(--text-secondary)' }}>Light</span>
            </button>
          </div>
        </GlassPanel>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Accent Color</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Primary accent color throughout the interface</p>
        <GlassPanel className="p-4">
          <div className="flex gap-3">
            {ACCENT_COLORS.map((accent) => (
              <button
                key={accent.id}
                onClick={() => updateSettings({ accentColor: accent.id as Settings['accentColor'] })}
                className="flex flex-col items-center gap-1.5 p-2 rounded-lg transition-all"
                style={{
                  background: settings.accentColor === accent.id ? 'rgba(255,255,255,0.05)' : 'transparent',
                  border: `2px solid ${settings.accentColor === accent.id ? accent.color : 'transparent'}`,
                }}
              >
                <div className="w-8 h-8 rounded-full" style={{ background: accent.color }} />
                <span className="text-[10px]" style={{ color: settings.accentColor === accent.id ? accent.color : 'var(--text-muted)' }}>
                  {accent.label}
                </span>
              </button>
            ))}
          </div>
        </GlassPanel>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Font Size</h3>
        <GlassPanel className="p-4">
          <div className="flex gap-3">
            {FONT_SIZES.map((size) => (
              <button
                key={size.id}
                onClick={() => updateSettings({ fontSize: size.id as Settings['fontSize'] })}
                className="flex-1 py-2 rounded-lg text-center transition-all"
                style={{
                  background: settings.fontSize === size.id ? 'rgba(129,140,248,0.1)' : 'var(--glass-bg)',
                  border: `1px solid ${settings.fontSize === size.id ? 'rgba(129,140,248,0.3)' : 'var(--glass-border)'}`,
                  color: settings.fontSize === size.id ? 'var(--accent-blue)' : 'var(--text-secondary)',
                }}
              >
                <span className="text-xs font-medium">{size.label}</span>
              </button>
            ))}
          </div>
        </GlassPanel>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Animations</h3>
        <GlassPanel className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Enable Animations</span>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>Transitions, counters, and effects</p>
            </div>
            <button
              role="switch"
              aria-checked={settings.enableAnimations}
              aria-label="Enable Animations"
              onClick={() => updateSettings({ enableAnimations: !settings.enableAnimations })}
              className="w-10 h-5 rounded-full transition-colors relative"
              style={{ background: settings.enableAnimations ? 'var(--accent-blue)' : 'var(--bg-tertiary)' }}
            >
              <div className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all" style={{ left: settings.enableAnimations ? 20 : 2 }} />
            </button>
          </div>
        </GlassPanel>
      </div>
    </div>
  )
}
