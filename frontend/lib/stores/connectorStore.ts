import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ConnectorType = 'notion' | 'google-drive' | 'confluence'
export type ConnectorStatus = 'connected' | 'disconnected'
export type SyncFrequency = '1h' | '3h' | '6h' | '12h' | '24h'

export interface ConnectorConfig {
  readonly type: ConnectorType
  readonly status: ConnectorStatus
  readonly syncFrequency: SyncFrequency
  readonly lastSync: string | null
  readonly enabled: boolean
}

interface ConnectorState {
  readonly connectors: Record<ConnectorType, ConnectorConfig>
  updateConnector: (type: ConnectorType, updates: Partial<Omit<ConnectorConfig, 'type'>>) => void
}

const defaultConnectors: Record<ConnectorType, ConnectorConfig> = {
  notion: {
    type: 'notion',
    status: 'disconnected',
    syncFrequency: '6h',
    lastSync: null,
    enabled: false,
  },
  'google-drive': {
    type: 'google-drive',
    status: 'disconnected',
    syncFrequency: '6h',
    lastSync: null,
    enabled: false,
  },
  confluence: {
    type: 'confluence',
    status: 'disconnected',
    syncFrequency: '6h',
    lastSync: null,
    enabled: false,
  },
}

export const useConnectorStore = create<ConnectorState>()(
  persist(
    (set) => ({
      connectors: defaultConnectors,

      updateConnector: (type: ConnectorType, updates: Partial<Omit<ConnectorConfig, 'type'>>) =>
        set((state) => ({
          connectors: {
            ...state.connectors,
            [type]: { ...state.connectors[type], ...updates },
          },
        })),
    }),
    {
      name: 'manic-ai-connectors',
      partialize: (state) => ({ connectors: state.connectors }),
    }
  )
)
