'use client'
import { useEffect } from 'react'
import { useChatStore } from '@/lib/store'
import { useCommandPaletteStore } from '@/lib/stores/commandPaletteStore'

export function useKeyboardShortcuts() {
  const { createConversation, setActiveView } = useChatStore()
  const { toggle: togglePalette, isOpen: paletteOpen, close: closePalette } = useCommandPaletteStore()

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable

      const ctrl = e.ctrlKey || e.metaKey

      // Command palette - works everywhere
      if (ctrl && e.key === 'k') {
        e.preventDefault()
        togglePalette()
        return
      }

      // Escape closes palette first, then navigates to chat
      if (e.key === 'Escape') {
        if (paletteOpen) {
          closePalette()
          return
        }
        if (!isInput) {
          setActiveView('chat')
        }
        return
      }

      // Don't trigger other shortcuts when typing in inputs
      if (isInput) return

      if (ctrl && e.key === 'n') {
        e.preventDefault()
        createConversation()
        setActiveView('chat')
      } else if (ctrl && e.key === 'd') {
        e.preventDefault()
        setActiveView('documents')
      } else if (ctrl && e.key === 'm') {
        e.preventDefault()
        setActiveView('models')
      } else if (ctrl && e.key === 'h') {
        e.preventDefault()
        setActiveView('dashboard')
      } else if (ctrl && e.key === 'r') {
        e.preventDefault()
        setActiveView('rag')
      } else if (ctrl && e.key === ',') {
        e.preventDefault()
        setActiveView('settings')
      } else if (ctrl && e.key === '.') {
        e.preventDefault()
        window.dispatchEvent(new CustomEvent('manic-refresh'))
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [createConversation, setActiveView, togglePalette, paletteOpen, closePalette])
}
