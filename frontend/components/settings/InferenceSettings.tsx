'use client'

import { useChatStore } from '@/lib/store'
import GlassPanel from '@/components/ui/GlassPanel'

const TEMP_PRESETS = [
  { label: 'Precise', value: 0.2, desc: 'Factual, deterministic' },
  { label: 'Balanced', value: 0.7, desc: 'Default, versatile' },
  { label: 'Creative', value: 1.2, desc: 'Imaginative, varied' },
]

export default function InferenceSettings() {
  const { settings, updateSettings } = useChatStore()

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Temperature</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Controls randomness in model outputs</p>

        {/* Presets */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          {TEMP_PRESETS.map((preset) => (
            <button
              key={preset.label}
              onClick={() => updateSettings({ temperature: preset.value })}
              className="p-3 rounded-lg text-center transition-all"
              style={{
                background: Math.abs(settings.temperature - preset.value) < 0.05 ? 'rgba(59,130,246,0.1)' : 'var(--glass-bg)',
                border: `1px solid ${Math.abs(settings.temperature - preset.value) < 0.05 ? 'rgba(59,130,246,0.3)' : 'var(--glass-border)'}`,
              }}
            >
              <div className="text-sm font-semibold" style={{ color: Math.abs(settings.temperature - preset.value) < 0.05 ? 'var(--accent-blue)' : 'var(--text-primary)' }}>
                {preset.label}
              </div>
              <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>{preset.desc}</div>
              <div className="text-xs font-mono mt-1" style={{ color: 'var(--text-muted)' }}>{preset.value}</div>
            </button>
          ))}
        </div>

        <GlassPanel className="p-4">
          <label className="flex items-center justify-between text-xs mb-2">
            <span style={{ color: 'var(--text-secondary)' }}>Custom Temperature</span>
            <span className="font-mono font-bold" style={{ color: 'var(--accent-blue)' }}>{settings.temperature.toFixed(2)}</span>
          </label>
          <input
            type="range" min={0} max={200} value={settings.temperature * 100}
            onChange={(e) => updateSettings({ temperature: parseInt(e.target.value) / 100 })}
            className="w-full accent-blue-500"
          />
          <div className="flex justify-between text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
            <span>0.0</span>
            <span>1.0</span>
            <span>2.0</span>
          </div>
        </GlassPanel>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Context Window</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Maximum tokens for model output</p>
        <GlassPanel className="p-4">
          <label className="flex items-center justify-between text-xs mb-2">
            <span style={{ color: 'var(--text-secondary)' }}>Max Tokens</span>
            <span className="font-mono font-bold" style={{ color: 'var(--accent-blue)' }}>{settings.maxTokens.toLocaleString()}</span>
          </label>
          <input
            type="range" min={256} max={16384} step={256}
            value={settings.maxTokens}
            onChange={(e) => updateSettings({ maxTokens: parseInt(e.target.value) })}
            className="w-full accent-blue-500"
          />
          <div className="flex justify-between text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
            <span>256</span>
            <span>8,192</span>
            <span>16,384</span>
          </div>
        </GlassPanel>
      </div>
    </div>
  )
}
