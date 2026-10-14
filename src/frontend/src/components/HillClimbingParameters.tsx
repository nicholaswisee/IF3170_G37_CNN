import type { HillClimbingVariant } from '../types/experiment'

export interface HillClimbingFormValues {
  variant: HillClimbingVariant
  max_iterations: string
  candidates_per_iteration: string
  max_sideways: string
  max_restarts: string
}

const hillClimbingVariantOptions: { value: HillClimbingVariant; label: string }[] = [
  { value: 'sideways', label: 'Sideways move (default)' },
  { value: 'steepest_ascent', label: 'Steepest ascent' },
  { value: 'stochastic', label: 'Stochastic' },
  { value: 'random_restart', label: 'Random restart' },
]

export function HillClimbingParameters({ values, onChange }: {
  values: HillClimbingFormValues
  onChange: (field: keyof HillClimbingFormValues, value: string) => void
}) {
  return (
    <>
      <label className="field-label" htmlFor="hc-variant">Hill climbing variant</label>
      <select id="hc-variant" value={values.variant} onChange={(event) => onChange('variant', event.currentTarget.value)}>
        {hillClimbingVariantOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <label className="field-label" htmlFor="hc-max-iterations">Maximum iterations (1–2000)</label>
      <input id="hc-max-iterations" type="number" min={1} max={2000} step={1} required value={values.max_iterations} onChange={(event) => onChange('max_iterations', event.currentTarget.value)} />
      <label className="field-label" htmlFor="hc-candidates">Candidates per iteration (1–50)</label>
      <input id="hc-candidates" type="number" min={1} max={50} step={1} required value={values.candidates_per_iteration} onChange={(event) => onChange('candidates_per_iteration', event.currentTarget.value)} />
      {values.variant === 'sideways' && (
        <>
          <label className="field-label" htmlFor="hc-max-sideways">Maximum sideways moves</label>
          <input id="hc-max-sideways" type="number" min={0} max={Number.MAX_SAFE_INTEGER} step={1} required value={values.max_sideways} onChange={(event) => onChange('max_sideways', event.currentTarget.value)} />
        </>
      )}
      {values.variant === 'random_restart' && (
        <>
          <label className="field-label" htmlFor="hc-max-restarts">Maximum restarts (0–20)</label>
          <input id="hc-max-restarts" type="number" min={0} max={20} step={1} required aria-describedby="hc-max-restarts-help" value={values.max_restarts} onChange={(event) => onChange('max_restarts', event.currentTarget.value)} />
          <p id="hc-max-restarts-help" className="field-help">Restarts after the first climb, so the run performs this many plus one climbs.</p>
        </>
      )}
    </>
  )
}
