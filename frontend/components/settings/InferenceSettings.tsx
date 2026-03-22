'use client'

import { useChatStore } from '@/lib/store'
import GlassPanel from '@/components/ui/GlassPanel'
import { useState } from 'react'

const TEMP_PRESETS = [
  { label: 'Precise', value: 0.2, desc: 'Factual, deterministic' },
  { label: 'Balanced', value: 0.7, desc: 'Default, versatile' },
  { label: 'Creative', value: 1.2, desc: 'Imaginative, varied' },
]

export default function InferenceSettings() {
  const { settings, updateSettings } = useChatStore()
  const [seedInput, setSeedInput] = useState(settings.seed !== null ? String(settings.seed) : '')

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
                background: Math.abs(settings.temperature - preset.value) < 0.05 ? 'rgba(129,140,248,0.1)' : 'var(--glass-bg)',
                border: `1px solid ${Math.abs(settings.temperature - preset.value) < 0.05 ? 'rgba(129,140,248,0.3)' : 'var(--glass-border)'}`,
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

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Top P</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Nucleus sampling — only tokens within this probability mass are considered</p>
        <GlassPanel className="p-4">
          <label className="flex items-center justify-between text-xs mb-2">
            <span style={{ color: 'var(--text-secondary)' }}>Top P</span>
            <span className="font-mono font-bold" style={{ color: 'var(--accent-blue)' }}>{settings.topP.toFixed(2)}</span>
          </label>
          <input
            type="range" min={0} max={100} step={5}
            value={Math.round(settings.topP * 100)}
            onChange={(e) => updateSettings({ topP: parseInt(e.target.value) / 100 })}
            className="w-full accent-blue-500"
          />
          <div className="flex justify-between text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
            <span>0.0</span>
            <span>0.5</span>
            <span>1.0</span>
          </div>
        </GlassPanel>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Repeat Penalty</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Penalises repetition — values above 1.0 reduce repetitive outputs</p>
        <GlassPanel className="p-4">
          <label className="flex items-center justify-between text-xs mb-2">
            <span style={{ color: 'var(--text-secondary)' }}>Repeat Penalty</span>
            <span className="font-mono font-bold" style={{ color: 'var(--accent-blue)' }}>{settings.repeatPenalty.toFixed(1)}</span>
          </label>
          <input
            type="range" min={50} max={200} step={10}
            value={Math.round(settings.repeatPenalty * 100)}
            onChange={(e) => updateSettings({ repeatPenalty: parseInt(e.target.value) / 100 })}
            className="w-full accent-blue-500"
          />
          <div className="flex justify-between text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
            <span>0.5</span>
            <span>1.0</span>
            <span>2.0</span>
          </div>
        </GlassPanel>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Seed</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Fixed seed for reproducible outputs — use Random for varied results</p>
        <GlassPanel className="p-4">
          <div className="flex items-center gap-3">
            <input
              type="number"
              disabled={settings.seed === null}
              value={seedInput}
              onChange={(e) => {
                setSeedInput(e.target.value)
                const parsed = parseInt(e.target.value)
                if (!isNaN(parsed)) updateSettings({ seed: parsed })
              }}
              placeholder="e.g. 42"
              className="flex-1 px-3 py-2 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/50 disabled:opacity-40"
              style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
            />
            <button
              onClick={() => {
                if (settings.seed === null) {
                  const s = Math.floor(Math.random() * 2_147_483_647)
                  setSeedInput(String(s))
                  updateSettings({ seed: s })
                } else {
                  setSeedInput('')
                  updateSettings({ seed: null })
                }
              }}
              className="px-3 py-2 rounded-lg text-xs font-semibold transition-all"
              style={{
                background: settings.seed === null ? 'rgba(129,140,248,0.1)' : 'var(--glass-bg)',
                border: `1px solid ${settings.seed === null ? 'rgba(129,140,248,0.3)' : 'var(--glass-border)'}`,
                color: settings.seed === null ? 'var(--accent-blue)' : 'var(--text-secondary)',
              }}
            >
              {settings.seed === null ? 'Random' : 'Fixed'}
            </button>
          </div>
          {settings.seed === null && (
            <p className="text-[10px] mt-2" style={{ color: 'var(--text-muted)' }}>Seed is random — click Fixed to pin a value</p>
          )}
        </GlassPanel>
      </div>
    </div>
  )
}
