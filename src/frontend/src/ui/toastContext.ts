import { createContext, useContext } from 'react'

export type ToastKind = 'info' | 'success' | 'error' | 'progress'

export interface ToastItem {
  id: number
  message: string
  kind: ToastKind
  leaving: boolean
}

export interface ToastApi {
  /** Shows a toast and returns its ID. Errors and progress stay until updated or dismissed. */
  show: (message: string, kind?: ToastKind, durationMs?: number) => number
  update: (id: number, message: string, kind: ToastKind, durationMs?: number) => void
  dismiss: (id: number) => void
}

export const ToastApiContext = createContext<ToastApi | null>(null)
export const ToastItemsContext = createContext<{ items: ToastItem[]; dismiss: (id: number) => void }>({ items: [], dismiss: () => {} })

export function useToast(): ToastApi {
  const api = useContext(ToastApiContext)
  if (!api) throw new Error('useToast must be used inside ToastProvider')
  return api
}
