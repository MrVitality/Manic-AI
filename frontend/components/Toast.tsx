'use client'
import { useState, useEffect, useCallback, createContext, useContext } from 'react'

type ToastType = 'info' | 'success' | 'error' | 'warning'

interface ToastItem {
  id: string
  message: string
  type: ToastType
}

interface ToastContextType {
  addToast: (message: string, type?: ToastType, duration?: number) => void
}

const ToastContext = createContext<ToastContextType>({ addToast: () => {} })

export function useToast() {
  return useContext(ToastContext)
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const addToast = useCallback((message: string, type: ToastType = 'info', duration = 5000) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration)
  }, [])

  const colors: Record<ToastType, string> = {
    info: 'bg-blue-500',
    success: 'bg-green-500',
    error: 'bg-red-500',
    warning: 'bg-yellow-500 text-black',
  }

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
        {toasts.map(toast => (
          <div
            key={toast.id}
            role="alert"
            className={`${colors[toast.type]} text-white px-4 py-3 rounded-lg shadow-lg text-sm animate-in slide-in-from-right duration-300`}
          >
            {toast.message}
            <button
              onClick={() => setToasts(prev => prev.filter(t => t.id !== toast.id))}
              className="ml-3 opacity-70 hover:opacity-100"
              aria-label="Dismiss"
            >
              x
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
