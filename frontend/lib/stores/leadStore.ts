import { create } from 'zustand'
import type { LeadSummary, LeadDetail, LeadFilter } from '@/types'

interface LeadState {
  leads: LeadSummary[]
  total: number
  isLoading: boolean
  error: string | null

  filter: LeadFilter
  setFilter: (filter: Partial<LeadFilter>) => void

  selectedLeadId: string | null
  selectedLead: LeadDetail | null
  isLoadingDetail: boolean
  setSelectedLeadId: (id: string | null) => void
  setSelectedLead: (lead: LeadDetail | null) => void

  setLeads: (leads: LeadSummary[], total: number) => void
  addLead: (lead: LeadSummary) => void
  setIsLoading: (loading: boolean) => void
  setIsLoadingDetail: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const useLeadStore = create<LeadState>()((set) => ({
  leads: [],
  total: 0,
  isLoading: false,
  error: null,

  filter: { tier: null, source: null, limit: 50, offset: 0 },
  setFilter: (filter) => set((state) => ({ filter: { ...state.filter, ...filter } })),

  selectedLeadId: null,
  selectedLead: null,
  isLoadingDetail: false,
  setSelectedLeadId: (id) => set({ selectedLeadId: id }),
  setSelectedLead: (lead) => set({ selectedLead: lead }),

  setLeads: (leads, total) => set({ leads, total }),
  addLead: (lead) => set((state) => ({ leads: [lead, ...state.leads], total: state.total + 1 })),
  setIsLoading: (loading) => set({ isLoading: loading }),
  setIsLoadingDetail: (loading) => set({ isLoadingDetail: loading }),
  setError: (error) => set({ error }),
}))
