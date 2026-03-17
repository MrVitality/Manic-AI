/**
 * Tests for the UI Zustand store.
 */
import { useUiStore } from '@/lib/stores/uiStore'

// Reset store before each test
beforeEach(() => {
  useUiStore.setState({
    isGenerating: false,
    error: null,
    sidebarCollapsed: false,
    useRag: false,
    serviceStatuses: {},
    settings: useUiStore.getState().settings, // keep defaults
  })
})

describe('uiStore', () => {
  describe('setIsGenerating', () => {
    it('should set isGenerating to true', () => {
      useUiStore.getState().setIsGenerating(true)
      expect(useUiStore.getState().isGenerating).toBe(true)
    })

    it('should set isGenerating to false', () => {
      useUiStore.getState().setIsGenerating(true)
      useUiStore.getState().setIsGenerating(false)
      expect(useUiStore.getState().isGenerating).toBe(false)
    })
  })

  describe('setError', () => {
    it('should set an error string', () => {
      useUiStore.getState().setError('Something broke')
      expect(useUiStore.getState().error).toBe('Something broke')
    })

    it('should clear error with null', () => {
      useUiStore.getState().setError('err')
      useUiStore.getState().setError(null)
      expect(useUiStore.getState().error).toBeNull()
    })
  })

  describe('setSidebarCollapsed', () => {
    it('should set sidebar collapsed state', () => {
      useUiStore.getState().setSidebarCollapsed(true)
      expect(useUiStore.getState().sidebarCollapsed).toBe(true)
    })
  })

  describe('toggleSidebar', () => {
    it('should toggle sidebar collapsed state', () => {
      expect(useUiStore.getState().sidebarCollapsed).toBe(false)
      useUiStore.getState().toggleSidebar()
      expect(useUiStore.getState().sidebarCollapsed).toBe(true)
      useUiStore.getState().toggleSidebar()
      expect(useUiStore.getState().sidebarCollapsed).toBe(false)
    })
  })

  describe('setUseRag', () => {
    it('should set RAG toggle', () => {
      useUiStore.getState().setUseRag(true)
      expect(useUiStore.getState().useRag).toBe(true)
    })
  })

  describe('setServiceStatuses', () => {
    it('should replace service statuses', () => {
      const statuses = {
        ollama: { name: 'Ollama', url: 'http://test', status: 'healthy' as const, latency_ms: 10 },
      }
      useUiStore.getState().setServiceStatuses(statuses)
      expect(useUiStore.getState().serviceStatuses).toEqual(statuses)
    })
  })

  describe('updateSettings', () => {
    it('should merge partial settings into existing settings', () => {
      const originalModel = useUiStore.getState().settings.defaultModel
      useUiStore.getState().updateSettings({ temperature: 0.9 })

      const settings = useUiStore.getState().settings
      expect(settings.temperature).toBe(0.9)
      expect(settings.defaultModel).toBe(originalModel) // unchanged
    })

    it('should update multiple settings at once', () => {
      useUiStore.getState().updateSettings({
        theme: 'light',
        fontSize: 'lg',
      })

      const settings = useUiStore.getState().settings
      expect(settings.theme).toBe('light')
      expect(settings.fontSize).toBe('lg')
    })
  })

  describe('default settings', () => {
    it('should have sensible defaults', () => {
      const settings = useUiStore.getState().settings
      expect(settings.defaultModel).toBe('llama3.2:3b')
      expect(settings.temperature).toBe(0.7)
      expect(settings.streamResponses).toBe(true)
      expect(settings.theme).toBe('dark')
    })
  })
})
