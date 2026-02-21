import { create } from 'zustand'

interface CommandPaletteState {
  isOpen: boolean
  query: string
  selectedIndex: number
  open: () => void
  close: () => void
  toggle: () => void
  setQuery: (query: string) => void
  setSelectedIndex: (index: number) => void
  reset: () => void
}

export const useCommandPaletteStore = create<CommandPaletteState>()((set) => ({
  isOpen: false,
  query: '',
  selectedIndex: 0,
  open: () => set({ isOpen: true, query: '', selectedIndex: 0 }),
  close: () => set({ isOpen: false, query: '', selectedIndex: 0 }),
  toggle: () =>
    set((state) => ({
      isOpen: !state.isOpen,
      query: state.isOpen ? '' : state.query,
      selectedIndex: 0,
    })),
  setQuery: (query) => set({ query, selectedIndex: 0 }),
  setSelectedIndex: (index) => set({ selectedIndex: index }),
  reset: () => set({ query: '', selectedIndex: 0 }),
}))
