'use client'
import { useState, useEffect, useCallback } from 'react'
import { useUiStore } from '@/lib/stores/uiStore'
import { checkHealth, fetchModels, invalidateApiUrlCache } from '@/lib/api'
import type { Model } from '@/types'

type DetectState = 'idle' | 'checking' | 'ok' | 'fail'

interface Props {
  onComplete: () => void
}

const TOTAL_STEPS = 4

// Inline spinner using CSS animation
const Spinner = () => (
  <span
    style={{
      display: 'inline-block',
      width: 14,
      height: 14,
      border: '2px solid var(--border-color)',
      borderTopColor: 'var(--accent-blue)',
      borderRadius: '50%',
      animation: 'wizard-spin 0.7s linear infinite',
      flexShrink: 0,
    }}
  />
)

function StatusIcon({ state }: { state: DetectState }) {
  if (state === 'checking') return <Spinner />
  if (state === 'ok') {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
        <circle cx="8" cy="8" r="7" fill="#10b981" fillOpacity="0.15" stroke="#10b981" strokeWidth="1.5" />
        <path d="M5 8l2.5 2.5L11 5.5" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
  if (state === 'fail') {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
        <circle cx="8" cy="8" r="7" fill="#ef4444" fillOpacity="0.15" stroke="#ef4444" strokeWidth="1.5" />
        <path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    )
  }
  return <span style={{ width: 16, height: 16, flexShrink: 0 }} />
}

// ─── Step 1: Connection ────────────────────────────────────────────────────────
function StepConnection({
  apiUrl,
  onApiUrlChange,
  apiState,
  onTest,
}: {
  apiUrl: string
  onApiUrlChange: (v: string) => void
  apiState: DetectState
  onTest: () => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6, marginBottom: 20 }}>
          Manic AI connects to the FastAPI backend to handle chat, RAG, and model management.
          The auto-detection below checks whether the API is reachable at the configured URL.
        </p>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '10px 14px',
            borderRadius: 8,
            background: 'var(--bg-elevated)',
            border: `1px solid ${apiState === 'ok' ? '#10b981' : apiState === 'fail' ? '#ef4444' : 'var(--border-color)'}`,
            marginBottom: 16,
          }}
        >
          <StatusIcon state={apiState} />
          <span style={{ fontSize: 13, color: 'var(--text-primary)', flex: 1 }}>{apiUrl}</span>
          {apiState === 'ok' && (
            <span style={{ fontSize: 11, color: '#10b981', fontWeight: 600, letterSpacing: '0.04em' }}>
              AUTO-DETECTED
            </span>
          )}
          {apiState === 'fail' && (
            <span style={{ fontSize: 11, color: '#ef4444', fontWeight: 600, letterSpacing: '0.04em' }}>
              NOT REACHABLE
            </span>
          )}
        </div>
        <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
          API URL
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="text"
            value={apiUrl}
            onChange={(e) => onApiUrlChange(e.target.value)}
            placeholder="http://localhost:8081"
            style={{
              flex: 1,
              padding: '8px 12px',
              borderRadius: 6,
              border: '1px solid var(--border-color)',
              background: 'var(--bg-elevated)',
              color: 'var(--text-primary)',
              fontSize: 13,
              outline: 'none',
            }}
          />
          <button
            onClick={onTest}
            disabled={apiState === 'checking'}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: '1px solid var(--accent-blue)',
              background: 'transparent',
              color: 'var(--accent-blue)',
              fontSize: 13,
              cursor: apiState === 'checking' ? 'default' : 'pointer',
              opacity: apiState === 'checking' ? 0.6 : 1,
              whiteSpace: 'nowrap',
            }}
          >
            Test Connection
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Step 2: Models ────────────────────────────────────────────────────────────
function StepModels({
  models,
  modelState,
  selectedModel,
  onSelectModel,
}: {
  models: Model[]
  modelState: DetectState
  selectedModel: string
  onSelectModel: (name: string) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6, margin: 0 }}>
        Select the default model used for chat. Models are served by Ollama and auto-detected from your instance.
      </p>
      {modelState === 'checking' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-muted)', fontSize: 13 }}>
          <Spinner /> Detecting available models...
        </div>
      )}
      {modelState !== 'checking' && models.length === 0 && (
        <div
          style={{
            padding: 16,
            borderRadius: 8,
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-color)',
          }}
        >
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: '0 0 12px' }}>
            No models detected. Make sure Ollama is running and has models pulled.
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: 12, margin: '0 0 6px' }}>Recommended models:</p>
          <code
            style={{
              display: 'block',
              padding: '8px 12px',
              borderRadius: 6,
              background: 'var(--bg-primary)',
              color: 'var(--accent-blue)',
              fontSize: 12,
              fontFamily: 'monospace',
              marginBottom: 6,
            }}
          >
            ollama pull llama3.2:3b
          </code>
          <code
            style={{
              display: 'block',
              padding: '8px 12px',
              borderRadius: 6,
              background: 'var(--bg-primary)',
              color: 'var(--accent-blue)',
              fontSize: 12,
              fontFamily: 'monospace',
            }}
          >
            ollama pull bge-m3
          </code>
        </div>
      )}
      {models.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {models.map((m) => (
            <button
              key={m.name}
              onClick={() => onSelectModel(m.name)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 14px',
                borderRadius: 8,
                border: `1px solid ${selectedModel === m.name ? 'var(--accent-blue)' : 'var(--border-color)'}`,
                background: selectedModel === m.name ? 'rgba(59,130,246,0.08)' : 'var(--bg-elevated)',
                color: 'var(--text-primary)',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <StatusIcon state="ok" />
              <span style={{ flex: 1, fontSize: 13 }}>{m.name}</span>
              <span style={{ fontSize: 11, color: '#10b981', fontWeight: 600, letterSpacing: '0.04em' }}>
                AUTO-DETECTED
              </span>
              {selectedModel === m.name && (
                <span style={{ fontSize: 11, color: 'var(--accent-blue)', fontWeight: 600 }}>DEFAULT</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Step 3: Authentication ────────────────────────────────────────────────────
function StepAuth({
  apiKey,
  onApiKeyChange,
  keyState,
  onTestKey,
}: {
  apiKey: string
  onApiKeyChange: (v: string) => void
  keyState: DetectState
  onTestKey: () => void
}) {
  const [showKey, setShowKey] = useState(false)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6, margin: 0 }}>
        Enter your API key to authenticate with the backend. If running in single-key mode, use the{' '}
        <code
          style={{
            padding: '1px 5px',
            borderRadius: 4,
            background: 'var(--bg-elevated)',
            color: 'var(--accent-blue)',
            fontSize: 12,
            fontFamily: 'monospace',
          }}
        >
          API_SECRET_KEY
        </code>{' '}
        from your <code style={{ padding: '1px 5px', borderRadius: 4, background: 'var(--bg-elevated)', fontSize: 12, fontFamily: 'monospace', color: 'var(--text-muted)' }}>.env</code> file. This step is optional — you can skip it if your API runs without authentication.
      </p>
      <div>
        <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
          API Key
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <input
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => onApiKeyChange(e.target.value)}
              placeholder="sk-..."
              style={{
                width: '100%',
                padding: '8px 36px 8px 12px',
                borderRadius: 6,
                border: '1px solid var(--border-color)',
                background: 'var(--bg-elevated)',
                color: 'var(--text-primary)',
                fontSize: 13,
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              style={{
                position: 'absolute',
                right: 8,
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: 2,
                fontSize: 12,
              }}
              aria-label={showKey ? 'Hide API key' : 'Show API key'}
            >
              {showKey ? 'Hide' : 'Show'}
            </button>
          </div>
          <button
            onClick={onTestKey}
            disabled={keyState === 'checking' || !apiKey}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: '1px solid var(--accent-blue)',
              background: 'transparent',
              color: 'var(--accent-blue)',
              fontSize: 13,
              cursor: keyState === 'checking' || !apiKey ? 'default' : 'pointer',
              opacity: keyState === 'checking' || !apiKey ? 0.5 : 1,
              whiteSpace: 'nowrap',
            }}
          >
            Test Key
          </button>
        </div>
        {keyState !== 'idle' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10 }}>
            <StatusIcon state={keyState} />
            <span style={{ fontSize: 12, color: keyState === 'ok' ? '#10b981' : keyState === 'fail' ? '#ef4444' : 'var(--text-muted)' }}>
              {keyState === 'checking' && 'Verifying key...'}
              {keyState === 'ok' && 'Key accepted — API is reachable'}
              {keyState === 'fail' && 'Key rejected or API unreachable'}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Step 4: Complete ──────────────────────────────────────────────────────────
function StepComplete({
  apiUrl,
  apiState,
  models,
  selectedModel,
  keyState,
  hasKey,
}: {
  apiUrl: string
  apiState: DetectState
  models: Model[]
  selectedModel: string
  keyState: DetectState
  hasKey: boolean
}) {
  const rows: Array<{ label: string; value: string; state: DetectState }> = [
    {
      label: 'API Endpoint',
      value: apiUrl,
      state: apiState,
    },
    {
      label: 'Default Model',
      value: selectedModel || 'None selected',
      state: models.length > 0 ? 'ok' : 'fail',
    },
    {
      label: 'Authentication',
      value: hasKey ? (keyState === 'ok' ? 'Key verified' : 'Key set (unverified)') : 'No key — open access',
      state: hasKey ? (keyState === 'ok' ? 'ok' : 'idle') : 'idle',
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6, margin: 0 }}>
        Setup is complete. Here is a summary of what was configured. You can change any of these settings later in the Settings panel.
      </p>
      <div
        style={{
          borderRadius: 8,
          border: '1px solid var(--border-color)',
          overflow: 'hidden',
        }}
      >
        {rows.map((row, i) => (
          <div
            key={row.label}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '12px 16px',
              background: i % 2 === 0 ? 'var(--bg-elevated)' : 'transparent',
              borderTop: i > 0 ? '1px solid var(--border-color)' : 'none',
            }}
          >
            <StatusIcon state={row.state} />
            <span style={{ fontSize: 12, color: 'var(--text-muted)', width: 120, flexShrink: 0 }}>
              {row.label}
            </span>
            <span style={{ fontSize: 13, color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Main Wizard ───────────────────────────────────────────────────────────────
export default function SetupWizard({ onComplete }: Props) {
  const settings = useUiStore((s) => s.settings)
  const updateSettings = useUiStore((s) => s.updateSettings)

  const [step, setStep] = useState(1)
  const [apiUrl, setApiUrl] = useState(settings.apiUrl)
  const [apiState, setApiState] = useState<DetectState>('idle')
  const [models, setModels] = useState<Model[]>([])
  const [modelState, setModelState] = useState<DetectState>('idle')
  const [selectedModel, setSelectedModel] = useState(settings.defaultModel)
  const [apiKey, setApiKey] = useState(settings.apiKey)
  const [keyState, setKeyState] = useState<DetectState>('idle')

  // Auto-detect on step entry
  const runConnectionCheck = useCallback(async (url?: string) => {
    const target = url ?? apiUrl
    updateSettings({ apiUrl: target })
    invalidateApiUrlCache()
    setApiState('checking')
    const ok = await checkHealth()
    setApiState(ok ? 'ok' : 'fail')
  }, [apiUrl, updateSettings])

  const runModelDetect = useCallback(async () => {
    setModelState('checking')
    try {
      const list = await fetchModels()
      setModels(list)
      setModelState(list.length > 0 ? 'ok' : 'fail')
      if (list.length > 0 && !selectedModel) {
        setSelectedModel(list[0].name)
      }
    } catch {
      setModels([])
      setModelState('fail')
    }
  }, [selectedModel])

  useEffect(() => {
    if (step === 1) runConnectionCheck()
    if (step === 2) runModelDetect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step])

  const handleTestKey = async () => {
    // Temporarily persist the key so checkHealth picks it up via getApiKey()
    updateSettings({ apiKey })
    setKeyState('checking')
    const ok = await checkHealth()
    setKeyState(ok ? 'ok' : 'fail')
  }

  const handleNext = () => {
    if (step === 1) {
      updateSettings({ apiUrl })
      invalidateApiUrlCache()
    }
    if (step < TOTAL_STEPS) setStep((s) => s + 1)
  }

  const handleBack = () => {
    if (step > 1) setStep((s) => s - 1)
  }

  const handleSkip = () => {
    if (step < TOTAL_STEPS) setStep((s) => s + 1)
  }

  const handleFinish = () => {
    updateSettings({ defaultModel: selectedModel, apiKey })
    invalidateApiUrlCache()
    onComplete()
  }

  const stepTitles = ['API Connection', 'Models', 'Authentication', 'Setup Complete']

  return (
    <>
      <style>{`
        @keyframes wizard-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>

      {/* Full-screen overlay */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 200,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(0,0,0,0.65)',
          backdropFilter: 'blur(6px)',
          padding: 16,
        }}
      >
        {/* Card */}
        <div
          style={{
            width: '100%',
            maxWidth: 520,
            borderRadius: 16,
            border: '1px solid var(--border-color)',
            background: 'var(--bg-secondary)',
            boxShadow: '0 24px 80px rgba(0,0,0,0.5)',
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '20px 24px 16px',
              borderBottom: '1px solid var(--border-color)',
              background: 'var(--glass-bg)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: 'var(--text-primary)' }}>
                  Manic AI Setup
                </h2>
                <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>
                  {stepTitles[step - 1]} — Step {step} of {TOTAL_STEPS}
                </p>
              </div>
              <div
                style={{
                  padding: '4px 10px',
                  borderRadius: 20,
                  border: '1px solid var(--border-color)',
                  fontSize: 11,
                  color: 'var(--text-muted)',
                  fontWeight: 600,
                }}
              >
                {step} / {TOTAL_STEPS}
              </div>
            </div>

            {/* Progress bar */}
            <div
              style={{
                height: 3,
                borderRadius: 2,
                background: 'var(--bg-elevated)',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  borderRadius: 2,
                  background: 'var(--accent-blue)',
                  width: `${(step / TOTAL_STEPS) * 100}%`,
                  transition: 'width 0.3s ease',
                }}
              />
            </div>

            {/* Step dots */}
            <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
              {Array.from({ length: TOTAL_STEPS }, (_, i) => (
                <div
                  key={i}
                  style={{
                    height: 4,
                    flex: 1,
                    borderRadius: 2,
                    background: i < step ? 'var(--accent-blue)' : 'var(--bg-elevated)',
                    transition: 'background 0.3s ease',
                  }}
                />
              ))}
            </div>
          </div>

          {/* Body */}
          <div style={{ padding: '24px 24px 8px' }}>
            {step === 1 && (
              <StepConnection
                apiUrl={apiUrl}
                onApiUrlChange={setApiUrl}
                apiState={apiState}
                onTest={() => runConnectionCheck(apiUrl)}
              />
            )}
            {step === 2 && (
              <StepModels
                models={models}
                modelState={modelState}
                selectedModel={selectedModel}
                onSelectModel={setSelectedModel}
              />
            )}
            {step === 3 && (
              <StepAuth
                apiKey={apiKey}
                onApiKeyChange={setApiKey}
                keyState={keyState}
                onTestKey={handleTestKey}
              />
            )}
            {step === 4 && (
              <StepComplete
                apiUrl={apiUrl}
                apiState={apiState}
                models={models}
                selectedModel={selectedModel}
                keyState={keyState}
                hasKey={!!apiKey}
              />
            )}
          </div>

          {/* Footer */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '16px 24px 20px',
            }}
          >
            <div>
              {step > 1 && step < TOTAL_STEPS && (
                <button
                  onClick={handleBack}
                  style={{
                    padding: '8px 16px',
                    borderRadius: 8,
                    border: '1px solid var(--border-color)',
                    background: 'transparent',
                    color: 'var(--text-secondary)',
                    fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  Back
                </button>
              )}
            </div>

            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {step < TOTAL_STEPS && (
                <button
                  onClick={handleSkip}
                  style={{
                    padding: '8px 14px',
                    borderRadius: 8,
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--text-muted)',
                    fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  Skip
                </button>
              )}

              {step < TOTAL_STEPS ? (
                <button
                  onClick={handleNext}
                  style={{
                    padding: '8px 20px',
                    borderRadius: 8,
                    border: 'none',
                    background: 'var(--accent-blue)',
                    color: '#fff',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Next
                </button>
              ) : (
                <button
                  onClick={handleFinish}
                  style={{
                    padding: '8px 20px',
                    borderRadius: 8,
                    border: 'none',
                    background: 'var(--accent-blue)',
                    color: '#fff',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Start Using Manic AI
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
