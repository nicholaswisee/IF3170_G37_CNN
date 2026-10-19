import { useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import { Icon } from './Icon'
import { ToastApiContext, ToastItemsContext, type ToastItem, type ToastKind } from './toastContext'

const DEFAULT_DURATION_MS = 3200
const EXIT_MS = 260
const MAX_VISIBLE = 3

/** Owns the toast queue. Info and success toasts close on their own; errors and progress wait. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const timers = useRef(new Map<number, number>())
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => {
    window.clearTimeout(timers.current.get(id))
    timers.current.delete(id)
    setItems((list) => list.map((item) => item.id === id ? { ...item, leaving: true } : item))
    window.setTimeout(() => setItems((list) => list.filter((item) => item.id !== id)), EXIT_MS)
  }, [])

  const schedule = useCallback((id: number, kind: ToastKind, durationMs?: number) => {
    window.clearTimeout(timers.current.get(id))
    if (kind === 'info' || kind === 'success') timers.current.set(id, window.setTimeout(() => dismiss(id), durationMs ?? DEFAULT_DURATION_MS))
  }, [dismiss])

  const show = useCallback((message: string, kind: ToastKind = 'info', durationMs?: number) => {
    const id = nextId.current
    nextId.current += 1
    setItems((list) => [...list.filter((item) => !item.leaving).slice(-(MAX_VISIBLE - 1)), { id, message, kind, leaving: false }])
    schedule(id, kind, durationMs)
    return id
  }, [schedule])

  const update = useCallback((id: number, message: string, kind: ToastKind, durationMs?: number) => {
    setItems((list) => list.some((item) => item.id === id)
      ? list.map((item) => item.id === id ? { ...item, message, kind } : item)
      : [...list.slice(-(MAX_VISIBLE - 1)), { id, message, kind, leaving: false }])
    schedule(id, kind, durationMs)
  }, [schedule])

  const api = useMemo(() => ({ show, update, dismiss }), [show, update, dismiss])
  const state = useMemo(() => ({ items, dismiss }), [items, dismiss])

  return (
    <ToastApiContext.Provider value={api}>
      <ToastItemsContext.Provider value={state}>{children}</ToastItemsContext.Provider>
    </ToastApiContext.Provider>
  )
}

const ICON_FOR: Record<Exclude<ToastKind, 'progress'>, 'info' | 'check' | 'alert'> = { info: 'info', success: 'check', error: 'alert' }

/** Capsule toasts stacked above the playback bar. */
export function ToastViewport() {
  const { items, dismiss } = useContext(ToastItemsContext)
  return (
    <div className="center-lane toast-lane" aria-live="polite">
      {items.map((item) => (
        <div key={item.id} className={`toast glass ${item.kind}${item.leaving ? ' leaving' : ''}`} role={item.kind === 'error' ? 'alert' : 'status'}>
          {item.kind === 'progress' ? <span className="spinner" aria-hidden="true" /> : <Icon name={ICON_FOR[item.kind]} size={18} />}
          <span className="toast-message">{item.message}</span>
          {item.kind === 'error' && (
            <button className="icon-btn" type="button" aria-label="Dismiss message" onClick={() => dismiss(item.id)}><Icon name="close" size={16} /></button>
          )}
        </div>
      ))}
    </div>
  )
}
