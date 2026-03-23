import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

export type ArtifactType = 'code' | 'markdown' | 'html'

export interface Artifact {
  id: string
  type: ArtifactType
  title: string
  content: string
  language?: string
  createdAt: Date
}

interface ArtifactState {
  artifacts: Artifact[]
  activeArtifactId: string | null
  isArtifactPanelOpen: boolean

  addArtifact: (artifact: Artifact) => void
  setActiveArtifact: (id: string | null) => void
  closePanel: () => void
  removeArtifact: (id: string) => void
  clearArtifacts: () => void
}

export const useArtifactStore = create<ArtifactState>()(
  persist(
    (set) => ({
      artifacts: [],
      activeArtifactId: null,
      isArtifactPanelOpen: false,

      addArtifact: (artifact: Artifact) =>
        set((state) => ({
          artifacts: [...state.artifacts, artifact],
          activeArtifactId: artifact.id,
          isArtifactPanelOpen: true,
        })),

      setActiveArtifact: (id: string | null) =>
        set({
          activeArtifactId: id,
          isArtifactPanelOpen: id !== null,
        }),

      closePanel: () =>
        set({
          isArtifactPanelOpen: false,
        }),

      removeArtifact: (id: string) =>
        set((state) => {
          const filtered = state.artifacts.filter((a) => a.id !== id)
          const newActiveId =
            state.activeArtifactId === id
              ? filtered.length > 0
                ? filtered[filtered.length - 1].id
                : null
              : state.activeArtifactId
          return {
            artifacts: filtered,
            activeArtifactId: newActiveId,
            isArtifactPanelOpen: newActiveId !== null,
          }
        }),

      clearArtifacts: () =>
        set({
          artifacts: [],
          activeArtifactId: null,
          isArtifactPanelOpen: false,
        }),
    }),
    {
      name: 'manic-ai-artifacts',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        artifacts: state.artifacts,
        activeArtifactId: state.activeArtifactId,
      }),
    }
  )
)
