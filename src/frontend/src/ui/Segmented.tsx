import { useLayoutEffect, useRef, type ReactNode } from 'react'
import { prefersReducedMotion } from './motion'

export interface SegmentOption<T extends string> {
  value: T
  label: ReactNode
}

interface SegmentedProps<T extends string> {
  /** Accessible name of the group. */
  label: string
  options: readonly SegmentOption<T>[]
  value: T
  onChange: (value: T) => void
  className?: string
  disabled?: boolean
}

// Same spring as --spring in tokens.css, with a plain overshoot curve for browsers without linear().
const SPRING = 'linear(0, 0.006, 0.025 2.8%, 0.101 6.1%, 0.539 18.9%, 0.721 25.3%, 0.849 31.5%, 0.937 38.1%, 0.968 41.8%, 0.991 45.7%, 1.006 50.1%, 1.015 55%, 1.017 63.9%, 1.001)'
const FALLBACK_EASING = 'cubic-bezier(0.34, 1.3, 0.64, 1)'
const SLIDE_MS = 560
// The thumb stays a lens for most of the slide, then settles back into a capsule.
const LENS_MS = 400
// Swell of the glass body during a slide. The label copy inside gets the inverse scale,
// so text inside the lens always lines up with the labels outside it and never doubles.
const SWELL: { scale: [number, number]; offset?: number }[] = [
  { scale: [1, 1] },
  { scale: [1.14, 1.2], offset: 0.3 },
  { scale: [1.04, 1.06], offset: 0.7 },
  { scale: [1, 1] },
]
const swellFrames = (invert: boolean): Keyframe[] => SWELL.map(({ scale: [x, y], offset }) => ({
  scale: invert ? `${1 / x} ${1 / y}` : `${x} ${y}`,
  ...(offset === undefined ? {} : { offset }),
}))

function springAnimate(element: Element, keyframes: Keyframe[], duration: number): Animation {
  try {
    return element.animate(keyframes, { duration, easing: SPRING })
  } catch {
    return element.animate(keyframes, { duration, easing: FALLBACK_EASING })
  }
}

/** Where the thumb is drawn right now, including mid animation. */
function currentPlacement(thumb: HTMLElement): { x: number; width: number } {
  const style = getComputedStyle(thumb)
  return { x: parseFloat(style.translate) || 0, width: parseFloat(style.width) || 0 }
}

/*
 * Segmented control with a liquid glass thumb. When the selection changes the
 * thumb slides on a spring while it swells into a clear glass lens, then
 * settles back into a white capsule. A copy of the labels rides inside the
 * thumb, aligned with the real labels, so the text stays crisp and single
 * through the glass. Motion runs on the Web Animations API so re-measuring or
 * class changes during a re-render can never cut a slide short, and a new
 * click mid slide continues from where the thumb is.
 */
export function Segmented<T extends string>({ label, options, value, onChange, className, disabled = false }: SegmentedProps<T>) {
  const trackRef = useRef<HTMLDivElement>(null)
  const thumbRef = useRef<HTMLSpanElement>(null)
  const lensTrackRef = useRef<HTMLSpanElement>(null)
  const placed = useRef(false)
  const running = useRef<Animation[]>([])
  const lensTimer = useRef<number | undefined>(undefined)

  useLayoutEffect(() => {
    const track = trackRef.current
    const thumb = thumbRef.current
    const lensTrack = lensTrackRef.current
    const lens = lensTrack?.parentElement
    if (!track || !thumb || !lensTrack || !lens) return

    // Positions the thumb and the magnified label copy at the selected option. Returns false before layout.
    const measure = () => {
      const buttons = Array.from(track.querySelectorAll<HTMLButtonElement>(':scope > button'))
      const selected = buttons.find((button) => button.getAttribute('aria-pressed') === 'true')
      if (!selected || track.clientWidth === 0) return null
      const copies = lensTrack.children
      buttons.forEach((button, index) => {
        const copy = copies[index] as HTMLElement | undefined
        if (!copy) return
        copy.style.left = `${button.offsetLeft}px`
        copy.style.width = `${button.offsetWidth}px`
      })
      lensTrack.style.width = `${track.clientWidth}px`
      return { x: selected.offsetLeft, width: selected.offsetWidth }
    }

    // The slide uses the translate property, which applies after scale, so the swell
    // always grows from the thumb's current center instead of drifting sideways.
    const settle = (target: { x: number; width: number }) => {
      thumb.style.translate = `${target.x}px 0`
      thumb.style.width = `${target.width}px`
      lensTrack.style.translate = `${-target.x}px 0`
      thumb.style.opacity = '1'
    }

    const target = measure()
    if (target) {
      const from = currentPlacement(thumb)
      const slides = placed.current && Math.abs(from.x - target.x) > 1 && !prefersReducedMotion()
      running.current.forEach((animation) => animation.cancel())
      running.current = []
      settle(target)
      if (slides) {
        running.current = [
          springAnimate(thumb, [
            { translate: `${from.x}px 0`, width: `${from.width}px` },
            { translate: `${target.x}px 0`, width: `${target.width}px` },
          ], SLIDE_MS),
          springAnimate(lensTrack, [{ translate: `${-from.x}px 0` }, { translate: `${-target.x}px 0` }], SLIDE_MS),
          // Swell into a lens and relax. scale is separate from transform, so it runs alongside the slide.
          thumb.animate(swellFrames(false), { duration: SLIDE_MS + 80, easing: 'ease-out' }),
          lens.animate(swellFrames(true), { duration: SLIDE_MS + 80, easing: 'ease-out' }),
        ]
        thumb.classList.add('lens')
        window.clearTimeout(lensTimer.current)
        lensTimer.current = window.setTimeout(() => thumb.classList.remove('lens'), LENS_MS)
      }
      placed.current = true
    }

    // Layout changes (panel resize, fonts loading) only re-place; they never animate or cancel a slide.
    const observer = new ResizeObserver(() => {
      const next = measure()
      if (next) settle(next)
    })
    observer.observe(track)
    return () => observer.disconnect()
  }, [value, options])

  return (
    <div ref={trackRef} className={className ? `seg ${className}` : 'seg'} role="group" aria-label={label}>
      {options.map((option) => (
        <button key={option.value} type="button" aria-pressed={option.value === value} disabled={disabled} onClick={() => onChange(option.value)}>
          {option.label}
        </button>
      ))}
      <span ref={thumbRef} className="seg-thumb" aria-hidden="true">
        <span className="seg-lens">
          <span ref={lensTrackRef} className="seg-lens-track">
            {options.map((option) => (
              <span key={option.value} className={option.value === value ? 'on' : undefined}>{option.label}</span>
            ))}
          </span>
        </span>
      </span>
    </div>
  )
}
