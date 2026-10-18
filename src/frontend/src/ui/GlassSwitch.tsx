import { useRef } from 'react'

interface GlassSwitchProps {
  id: string
  checked: boolean
  onChange: (checked: boolean) => void
  /** Accessible name when no visible label points at the input. */
  label?: string
  disabled?: boolean
}

/*
 * iOS style switch. Flipping it slides the knob on a spring while a one shot
 * keyframe animation swells it into a clear glass lens over the track and back
 * (see .switch in controls.css). Nothing waits on timers, so the knob never
 * holds the lens shape after the flip.
 */
export function GlassSwitch({ id, checked, onChange, label, disabled = false }: GlassSwitchProps) {
  const root = useRef<HTMLSpanElement>(null)

  const playFlip = () => {
    const element = root.current
    if (!element) return
    // Restart the animation even when flipping again before the last one ended.
    element.classList.remove('flip')
    void element.offsetWidth
    element.classList.add('flip')
  }

  return (
    <span
      ref={root}
      className="switch"
      onAnimationEnd={(event) => {
        if (event.animationName === 'knob-lens') event.currentTarget.classList.remove('flip')
      }}
    >
      <input
        id={id}
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        aria-label={label}
        onChange={(event) => {
          playFlip()
          onChange(event.currentTarget.checked)
        }}
      />
      <span className="switch-track" aria-hidden="true" />
      <span className="switch-knob" aria-hidden="true" />
    </span>
  )
}
