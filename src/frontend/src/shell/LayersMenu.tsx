import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Icon } from '../ui/Icon'
import { GlassSwitch } from '../ui/GlassSwitch'
import { Segmented } from '../ui/Segmented'
import type { ColorMode } from '../viewer/sceneModel'

export interface LayerToggles {
  labels: boolean
  grid: boolean
  trail: boolean
}

interface LayersMenuProps {
  colorMode: ColorMode
  onColorMode: (mode: ColorMode) => void
  toggles: LayerToggles
  onToggle: (key: keyof LayerToggles, value: boolean) => void
  glass: number
  onGlass: (value: number) => void
}

const COLOR_OPTIONS: { value: ColorMode; label: string }[] = [
  { value: 'identity', label: 'Package' },
  { value: 'value', label: 'Value' },
  { value: 'eta', label: 'ETA' },
  { value: 'fragile', label: 'Fragile' },
]

const TOGGLE_LABELS: Record<keyof LayerToggles, string> = { labels: 'Truck labels', grid: 'Floor grid', trail: 'Move trail' }
const GLASS_MIN = 0.35
const GLASS_MAX = 0.92

/** Bottom left Layers tile with display options for the 3D view and the glass tint. */
export function LayersMenu({ colorMode, onColorMode, toggles, onToggle, glass, onGlass }: LayersMenuProps) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false)
    }
    // Registered on document so it runs before the app's window shortcut and keeps Esc from also leaving truck view.
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.stopPropagation()
      setOpen(false)
    }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  const glassPercent = ((glass - GLASS_MIN) / (GLASS_MAX - GLASS_MIN)) * 100
  return (
    <div className="layers" ref={root}>
      {open && (
        <div className="popover glass" role="dialog" aria-label="Layers">
          <h3>Color packages by</h3>
          <Segmented label="Color packages by" options={COLOR_OPTIONS} value={colorMode} onChange={onColorMode} />
          <div className="group">
            {(Object.keys(TOGGLE_LABELS) as (keyof LayerToggles)[]).map((key) => (
              <div className="row" key={key}>
                <label className="row-label" htmlFor={`layer-${key}`}><span>{TOGGLE_LABELS[key]}</span></label>
                <GlassSwitch id={`layer-${key}`} checked={toggles[key]} onChange={(value) => onToggle(key, value)} />
              </div>
            ))}
          </div>
          <h3>Glass</h3>
          <div className="glass-range">
            <span>Clear</span>
            <input
              type="range"
              min={GLASS_MIN * 100}
              max={GLASS_MAX * 100}
              value={Math.round(glass * 100)}
              aria-label="Glass tint"
              style={{ '--fill': `${glassPercent}%` } as CSSProperties}
              onChange={(event) => onGlass(Number(event.currentTarget.value) / 100)}
            />
            <span>Tinted</span>
          </div>
        </div>
      )}
      <button className="layers-tile glass interactive" type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        <Icon name="layers" size={22} />Layers
      </button>
    </div>
  )
}
