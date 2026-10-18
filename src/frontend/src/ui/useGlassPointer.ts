import { useEffect } from 'react'

/** Lets the highlight on interactive glass controls follow the pointer (see .interactive in glass.css). */
export function useGlassPointer(): void {
  useEffect(() => {
    const follow = (event: PointerEvent) => {
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>('.interactive') : null
      if (!target) return
      const box = target.getBoundingClientRect()
      target.style.setProperty('--mx', `${event.clientX - box.left}px`)
      target.style.setProperty('--my', `${event.clientY - box.top}px`)
    }
    document.addEventListener('pointermove', follow, { passive: true })
    return () => document.removeEventListener('pointermove', follow)
  }, [])
}
