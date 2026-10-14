import { useId, useReducer, useState, type FormEvent } from 'react'
import type { Problem } from '../types/experiment'
import { createProblemForm, parseProblemForm, problemFormReducer, type ProblemFormAction } from './problemForm'

interface ProblemConfigurationProps {
  initialProblem: Problem
  onSubmit: (problem: Problem) => void | Promise<void>
  onDirtyChange?: (dirty: boolean) => void
  disabled?: boolean
}

interface ProblemFieldProps {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  error?: string
  numeric?: boolean
  minimum?: number
  integer?: boolean
}

function ProblemField({ id, label, value, onChange, error, numeric = false, minimum = 0, integer = false }: ProblemFieldProps) {
  return (
    <div>
      <label className="field-label" htmlFor={id}>{label}</label>
      <input
        id={id}
        type={numeric ? 'number' : 'text'}
        value={value}
        required
        min={numeric ? minimum : undefined}
        max={integer ? Number.MAX_SAFE_INTEGER : undefined}
        step={numeric ? integer ? 1 : 'any' : undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        onChange={(event) => onChange(event.currentTarget.value)}
      />
      {error && <p className="control-error" id={`${id}-error`}>{error}</p>}
    </div>
  )
}

export function ProblemConfiguration({ initialProblem, onSubmit, onDirtyChange, disabled = false }: ProblemConfigurationProps) {
  const prefix = useId()
  const [draft, updateDraft] = useReducer(problemFormReducer, initialProblem, createProblemForm)
  const [showErrors, setShowErrors] = useState(false)
  const [isApplying, setIsApplying] = useState(false)
  const [applied, setApplied] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const result = parseProblemForm(draft)
  const errors = showErrors ? result.errors : {}

  const dispatch = (action: ProblemFormAction) => {
    updateDraft(action)
    setApplied(false)
    setError(null)
    onDirtyChange?.(true)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (disabled || isApplying) return
    setShowErrors(true)
    setApplied(false)
    setError(null)
    onDirtyChange?.(true)
    if (!result.problem) return
    setIsApplying(true)
    try {
      await onSubmit(result.problem)
      onDirtyChange?.(false)
      setApplied(true)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not apply configuration.')
    } finally {
      setIsApplying(false)
    }
  }

  return (
    <section className="problem-configuration control-panel" aria-labelledby={`${prefix}-heading`}>
      <div className="panel-heading">
        <h2 id={`${prefix}-heading`}>Problem and fleet configuration</h2>
      </div>
      <form noValidate aria-busy={isApplying} onSubmit={(event) => void handleSubmit(event)}>
        <fieldset className="form-fields" disabled={disabled || isApplying}>
        <div className="problem-section-heading">
          <h3>Trucks ({draft.trucks.length})</h3>
          <button type="button" onClick={() => dispatch({ type: 'add-truck' })}>Add truck</button>
        </div>
        <p className="problem-help">Keep at least one truck. Dimensions are positive whole numbers; capacity may be zero.</p>
        {errors.trucks && <p className="control-error">{errors.trucks}</p>}
        <div className="problem-rows">
          {draft.trucks.map(({ key, values }, index) => (
            <fieldset className="problem-row" key={key}>
              <legend>Truck {index + 1}</legend>
              <div className="problem-fields">
                <ProblemField id={`${prefix}-truck-${key}-id`} label="Truck ID" value={values.id} error={errors[`trucks.${key}.id`]} onChange={(id) => dispatch({ type: 'update-truck', key, changes: { id } })} />
                {(['width', 'length', 'height'] as const).map((field) => (
                  <ProblemField key={field} id={`${prefix}-truck-${key}-${field}`} label={field} value={values[field]} numeric minimum={1} integer error={errors[`trucks.${key}.${field}`]} onChange={(value) => dispatch({ type: 'update-truck', key, changes: { [field]: value } })} />
                ))}
                <ProblemField id={`${prefix}-truck-${key}-capacity`} label="Max capacity" value={values.max_capacity} numeric error={errors[`trucks.${key}.max_capacity`]} onChange={(max_capacity) => dispatch({ type: 'update-truck', key, changes: { max_capacity } })} />
              </div>
              <button className="problem-remove" type="button" aria-label={`Remove truck ${index + 1}`} disabled={draft.trucks.length === 1} onClick={() => dispatch({ type: 'remove-truck', key })}>Remove truck</button>
            </fieldset>
          ))}
        </div>
        <div className="problem-section-heading">
          <h3>Packages ({draft.packages.length})</h3>
          <button type="button" onClick={() => dispatch({ type: 'add-package' })}>Add package</button>
        </div>
        <p className="problem-help">Package IDs must be unique. Value, weight, and ETA may be zero; ETA must be a whole number.</p>
        {draft.packages.length === 0 && <p className="problem-help">No packages added.</p>}
        <div className="problem-rows">
          {draft.packages.map(({ key, values }, index) => (
            <fieldset className="problem-row" key={key}>
              <legend>Package {index + 1}</legend>
              <div className="problem-fields">
                <ProblemField id={`${prefix}-package-${key}-id`} label="Package ID" value={values.id} error={errors[`packages.${key}.id`]} onChange={(id) => dispatch({ type: 'update-package', key, changes: { id } })} />
                {(['width', 'length', 'height'] as const).map((field) => (
                  <ProblemField key={field} id={`${prefix}-package-${key}-${field}`} label={field} value={values[field]} numeric minimum={1} integer error={errors[`packages.${key}.${field}`]} onChange={(value) => dispatch({ type: 'update-package', key, changes: { [field]: value } })} />
                ))}
                {(['value', 'weight', 'eta'] as const).map((field) => (
                  <ProblemField key={field} id={`${prefix}-package-${key}-${field}`} label={field === 'eta' ? 'ETA' : field} value={values[field]} numeric integer={field === 'eta'} error={errors[`packages.${key}.${field}`]} onChange={(value) => dispatch({ type: 'update-package', key, changes: { [field]: value } })} />
                ))}
                <label className="problem-checkbox" htmlFor={`${prefix}-package-${key}-fragile`}>
                  <input id={`${prefix}-package-${key}-fragile`} type="checkbox" checked={values.is_fragile} onChange={(event) => dispatch({ type: 'update-package', key, changes: { is_fragile: event.currentTarget.checked } })} />
                  Fragile
                </label>
              </div>
              <button className="problem-remove" type="button" aria-label={`Remove package ${index + 1}`} onClick={() => dispatch({ type: 'remove-package', key })}>Remove package</button>
            </fieldset>
          ))}
        </div>
        {showErrors && !result.problem && <p className="control-error" role="alert">Correct the highlighted fields before applying the configuration.</p>}
        <button className="run-button" type="submit">{isApplying ? 'Validating…' : 'Apply configuration'}</button>
        </fieldset>
        {error && <p className="control-error" role="alert">{error}</p>}
        {applied && <p className="problem-help" role="status">Configuration applied. Ready to run.</p>}
      </form>
    </section>
  )
}
