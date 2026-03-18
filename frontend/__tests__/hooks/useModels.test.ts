/**
 * Tests for useModels hook — verifies SWR integration.
 */
import { renderHook } from '@testing-library/react'

// Mock SWR to control behavior in tests
const mockMutate = jest.fn()
let swrResult = { isLoading: false, data: undefined as any, error: undefined as any, mutate: mockMutate }

jest.mock('swr', () => ({
  __esModule: true,
  default: jest.fn((_key: string, _fetcher: any, _opts: any) => swrResult),
}))

import useSWR from 'swr'
const mockUseSWR = useSWR as jest.MockedFunction<typeof useSWR>

// Mock the API module
jest.mock('@/lib/api', () => ({
  fetchModels: jest.fn(),
}))

import { fetchModels } from '@/lib/api'
const mockFetchModels = fetchModels as jest.MockedFunction<typeof fetchModels>

const mockStore = {
  models: [],
  selectedModel: '',
  isLoadingModels: false,
  setModels: jest.fn(),
  setSelectedModel: jest.fn(),
  setIsLoadingModels: jest.fn(),
  setError: jest.fn(),
}

jest.mock('@/lib/store', () => {
  const mockFn: any = jest.fn((selector?: any) =>
    typeof selector === 'function' ? selector(mockStore) : mockStore
  )
  mockFn.getState = jest.fn(() => mockStore)
  return { useChatStore: mockFn }
})

import { useModels } from '@/hooks/useModels'

beforeEach(() => {
  jest.clearAllMocks()
  swrResult = { isLoading: false, data: undefined, error: undefined, mutate: mockMutate }
  mockFetchModels.mockResolvedValue([{ name: 'llama3.2:3b', size: 0, digest: '', modified_at: '' }])
})

describe('useModels', () => {
  it('calls useSWR with "models" key and fetchModels fetcher', () => {
    renderHook(() => useModels())

    expect(mockUseSWR).toHaveBeenCalledWith(
      'models',
      mockFetchModels,
      expect.objectContaining({ dedupingInterval: expect.any(Number) })
    )
  })

  it('passes dedupingInterval to useSWR to prevent duplicate requests', () => {
    renderHook(() => useModels())

    const swrCall = (mockUseSWR as jest.Mock).mock.calls[0]
    const options = swrCall[2]
    expect(options.dedupingInterval).toBeGreaterThan(0)
  })

  it('passes refreshInterval to useSWR for periodic revalidation', () => {
    renderHook(() => useModels())

    const swrCall = (mockUseSWR as jest.Mock).mock.calls[0]
    const options = swrCall[2]
    expect(options.refreshInterval).toBeGreaterThan(0)
  })

  it('exposes isLoadingModels mapped from SWR isLoading', () => {
    swrResult = { ...swrResult, isLoading: true }
    const { result } = renderHook(() => useModels())
    expect(result.current.isLoadingModels).toBe(true)
  })

  it('exposes models array', () => {
    const { result } = renderHook(() => useModels())
    expect(Array.isArray(result.current.models)).toBe(true)
  })

  it('exposes refreshModels function that calls mutate', () => {
    const { result } = renderHook(() => useModels())
    expect(typeof result.current.refreshModels).toBe('function')
    result.current.refreshModels()
    expect(mockMutate).toHaveBeenCalled()
  })
})
