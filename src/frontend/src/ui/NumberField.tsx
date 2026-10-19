import { Icon } from './Icon'

interface NumberFieldProps {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  step: number
  integer: boolean
  min: number | null
  max: number | null
  disabled?: boolean
  invalid?: boolean
  placeholder?: string
  describedBy?: string
}

function decimals(step: number): number {
  const text = String(step)
  return text.includes('.') ? text.length - text.indexOf('.') - 1 : 0
}

/** Glass stepper: type a value or nudge it with the minus and plus buttons, clamped to the backend range. */
export function NumberField({ id, label, value, onChange, step, integer, min, max, disabled = false, invalid = false, placeholder, describedBy }: NumberFieldProps) {
  const bump = (direction: 1 | -1) => {
    const current = Number(value)
    const base = value.trim() !== '' && Number.isFinite(current) ? current : (min ?? 0)
    let next = base + direction * step
    if (min !== null) next = Math.max(min, next)
    if (max !== null) next = Math.min(max, next)
    onChange(String(Number(next.toFixed(decimals(step)))))
  }

  return (
    <div className={invalid ? 'stepper invalid' : 'stepper'}>
      <button type="button" aria-label={`Decrease ${label}`} disabled={disabled} onClick={() => bump(-1)}><Icon name="minus" size={15} /></button>
      <input
        id={id}
        type="text"
        inputMode={integer ? 'numeric' : 'decimal'}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        onChange={(event) => onChange(event.currentTarget.value)}
      />
      <button type="button" aria-label={`Increase ${label}`} disabled={disabled} onClick={() => bump(1)}><Icon name="plus" size={15} /></button>
    </div>
  )
}
