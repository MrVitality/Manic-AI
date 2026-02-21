'use client'
import { useEffect } from 'react'
import { useChatStore } from '@/lib/store'

export function useTheme() {
  const { settings, updateSettings } = useChatStore()
  const theme = settings.theme

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const toggleTheme = () => {
    updateSettings({ theme: theme === 'dark' ? 'light' : 'dark' })
  }

  const setTheme = (newTheme: 'dark' | 'light') => {
    updateSettings({ theme: newTheme })
  }

  return { theme, toggleTheme, setTheme }
}
