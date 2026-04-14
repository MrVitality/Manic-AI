import { create } from 'zustand'
import type { ListingSummary, ListingDetail, ListingFilter } from '@/types'

interface ListingState {
  listings: ListingSummary[]
  total: number
  isLoading: boolean
  error: string | null

  filter: ListingFilter
  setFilter: (filter: Partial<ListingFilter>) => void

  selectedListing: ListingDetail | null
  isLoadingDetail: boolean
  setSelectedListing: (listing: ListingDetail | null) => void
  setIsLoadingDetail: (loading: boolean) => void

  setListings: (listings: ListingSummary[], total: number) => void
  addListing: (listing: ListingSummary) => void
  setIsLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const useListingStore = create<ListingState>()((set) => ({
  listings: [],
  total: 0,
  isLoading: false,
  error: null,

  filter: { status: null, city: null, source: null, limit: 50, offset: 0 },
  setFilter: (filter) => set((state) => ({ filter: { ...state.filter, ...filter } })),

  selectedListing: null,
  isLoadingDetail: false,
  setSelectedListing: (listing) => set({ selectedListing: listing }),
  setIsLoadingDetail: (loading) => set({ isLoadingDetail: loading }),

  setListings: (listings, total) => set({ listings, total }),
  addListing: (listing) =>
    set((state) => ({ listings: [listing, ...state.listings], total: state.total + 1 })),
  setIsLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}))
