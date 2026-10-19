import { useEffect, useState, type ReactNode } from 'react'
import { prefersReducedMotion } from './motion'

/** Matches the longest exit animation in the stylesheets and the toast exit. */
export const EXIT_MS = 260

/**
 * Keeps the last shown children mounted for EXIT_MS after they turn falsy, with
 * data-leaving set so the stylesheet can play the closing animation.
 */
export function Presence({ children }: { children: ReactNode }) {
  const [shown, setShown] = useState<ReactNode>(children || null)
  const [leaving, setLeaving] = useState(false)
  // Derived from props during render so opening never lags a frame behind.
  if (children && children !== shown) {
    setShown(children)
    setLeaving(false)
  } else if (!children && shown && !leaving) {
    setLeaving(true)
  }

  useEffect(() => {
    if (!leaving) return
    const timer = window.setTimeout(() => {
      setShown(null)
      setLeaving(false)
    }, prefersReducedMotion() ? 0 : EXIT_MS)
    return () => window.clearTimeout(timer)
  }, [leaving])

  if (!shown) return null
  return <div className="presence" data-leaving={leaving || undefined}>{shown}</div>
}
