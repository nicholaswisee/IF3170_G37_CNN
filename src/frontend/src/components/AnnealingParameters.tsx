export interface AnnealingFormValues {
  initial_temperature: string
  alpha: string
  min_temperature: string
  max_iterations: string
  stuck_patience: string
}

export function AnnealingParameters({ values, onChange }: {
  values: AnnealingFormValues
  onChange: (field: keyof AnnealingFormValues, value: string) => void
}) {
  return (
    <>
      <label className="field-label" htmlFor="initial-temperature">Initial temperature (optional)</label>
      <input id="initial-temperature" type="number" min={0} step="any" placeholder="Automatic" aria-describedby="initial-temperature-help" value={values.initial_temperature} onChange={(event) => onChange('initial_temperature', event.currentTarget.value)} />
      <p id="initial-temperature-help" className="field-help">Leave empty to use the average package value, with a minimum of 1.</p>
      <label className="field-label" htmlFor="alpha">Cooling factor alpha (0 &lt; alpha &lt; 1)</label>
      <input id="alpha" type="number" min={0} max={1} step="any" required value={values.alpha} onChange={(event) => onChange('alpha', event.currentTarget.value)} />
      <label className="field-label" htmlFor="min-temperature">Minimum temperature</label>
      <input id="min-temperature" type="number" min={0} step="any" required value={values.min_temperature} onChange={(event) => onChange('min_temperature', event.currentTarget.value)} />
      <label className="field-label" htmlFor="max-iterations">Maximum iterations (1–5000)</label>
      <input id="max-iterations" type="number" min={1} max={5000} step={1} required value={values.max_iterations} onChange={(event) => onChange('max_iterations', event.currentTarget.value)} />
      <label className="field-label" htmlFor="stuck-patience">Stuck patience</label>
      <input id="stuck-patience" type="number" min={1} max={Number.MAX_SAFE_INTEGER} step={1} required value={values.stuck_patience} onChange={(event) => onChange('stuck_patience', event.currentTarget.value)} />
    </>
  )
}
