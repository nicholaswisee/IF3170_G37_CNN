import { useRef, useState } from 'react'
import { describeRange, highestValue, lowestValue } from '../api/limits'
import { buildRunRequest, defaultDrafts, parseParameters, parseSeed, visibleFields, type ParameterDrafts } from '../api/requests'
import { ALGORITHM_LABELS, ALGORITHM_SHORT_LABELS, OBJECTIVE_LABELS, VARIANT_LABELS, formatNumber, formatWhole } from '../copy/format'
import type { Algorithm, HillClimbingVariant, Limits, ObjectiveMode, Problem, RunExperimentRequest } from '../types/experiment'
import { GlassSwitch } from '../ui/GlassSwitch'
import { Icon } from '../ui/Icon'
import { NumberField } from '../ui/NumberField'
import { Segmented } from '../ui/Segmented'
import { useToast } from '../ui/toastContext'

const OFFICIAL_SEEDS = [42, 123, 2026] as const
const ALGORITHMS = (Object.keys(ALGORITHM_LABELS) as Algorithm[]).map((value) => ({ value, label: ALGORITHM_SHORT_LABELS[value] }))
const VARIANTS = Object.keys(VARIANT_LABELS) as HillClimbingVariant[]
const OBJECTIVES = (Object.keys(OBJECTIVE_LABELS) as ObjectiveMode[]).map((value) => ({ value, label: OBJECTIVE_LABELS[value] }))
const OBJECTIVE_HELP: Record<ObjectiveMode, string> = {
  total_value: 'Sum of the value of every loaded package. Used for the mandatory experiments.',
  eta_weighted_value: 'Each loaded package counts as value divided by ETA plus one, so urgent packages weigh more.',
}

interface SetupPanelProps {
  open: boolean
  problem: Problem
  isExampleProblem: boolean
  /** Name of the saved configuration the problem was loaded from, if it is unchanged. */
  configName: string | null
  /** True while the scene shows a run instead of this configured problem. */
  viewingRun: boolean
  limits: Limits | null
  limitsError: string | null
  running: boolean
  onRetryLimits: () => void
  onEditProblem: () => void
  onOpenConfigs: () => void
  onPreviewProblem: () => void
  onRun: (request: RunExperimentRequest, label: string) => void
}

/** Left panel: what to solve and how. Ranges and defaults come from the backend limits. */
export function SetupPanel({ open, problem, isExampleProblem, configName, viewingRun, limits, limitsError, running, onRetryLimits, onEditProblem, onOpenConfigs, onPreviewProblem, onRun }: SetupPanelProps) {
  const toast = useToast()
  const [algorithm, setAlgorithm] = useState<Algorithm>('simulated_annealing')
  const [variant, setVariant] = useState<HillClimbingVariant>('sideways')
  const [objective, setObjective] = useState<ObjectiveMode>('total_value')
  const [edited, setEdited] = useState<Partial<Record<Algorithm, ParameterDrafts>>>({})
  const [seedText, setSeedText] = useState('42')
  const [persist, setPersist] = useState(false)
  const [recordReplay, setRecordReplay] = useState(true)
  const [invalid, setInvalid] = useState<string[]>([])
  // The validation toast stays until the input is fixed or a run starts.
  const errorToast = useRef<number | null>(null)
  const clearErrorToast = () => {
    if (errorToast.current !== null) toast.dismiss(errorToast.current)
    errorToast.current = null
  }

  const drafts: ParameterDrafts = edited[algorithm] ?? (limits ? defaultDrafts(limits, algorithm) : {})
  const fields = limits ? visibleFields(algorithm, variant, limits) : []
  const totalValue = problem.packages.reduce((sum, pkg) => sum + pkg.value, 0)
  const totalWeight = problem.packages.reduce((sum, pkg) => sum + pkg.weight, 0)
  const capacity = problem.trucks.reduce((sum, truck) => sum + truck.max_capacity, 0)
  const meanValue = problem.packages.length ? totalValue / problem.packages.length : 1

  const setDraft = (key: string, value: string) => {
    setEdited((all) => ({ ...all, [algorithm]: { ...drafts, [key]: value } }))
    setInvalid((keys) => keys.filter((item) => item !== key))
    clearErrorToast()
  }

  const run = () => {
    if (!limits) return
    const parsed = parseParameters(algorithm, variant, drafts, limits)
    const seed = parseSeed(seedText, limits)
    setInvalid([...parsed.invalid, ...(seed.error ? ['seed'] : [])])
    const error = parsed.error ?? seed.error
    clearErrorToast()
    if (error) {
      errorToast.current = toast.show(error, 'error')
      return
    }
    const label = algorithm === 'hill_climbing' ? `${VARIANT_LABELS[variant]} Hill Climbing` : ALGORITHM_LABELS[algorithm]
    onRun(buildRunRequest({
      algorithm, problem, seed: seed.seed, parameters: parsed.parameters, objectiveMode: objective, variant,
      includeStateHistory: recordReplay, persist,
    }), `${label} with seed ${seed.seed}`)
  }

  return (
    <aside className="panel panel-left glass" aria-label="Setup" inert={!open}>
      <div className="panel-head">
        <h2>Setup</h2>
        {isExampleProblem && <span className="tag orange">Example problem</span>}
        {configName && <span className="tag blue truncate" title={configName}>{configName}</span>}
      </div>
      <div className="panel-body">
        <section>
          <div className="section-title">
            <span>Problem</span>
            <span className="section-actions">
              {viewingRun && <button className="btn btn-plain btn-sm" type="button" onClick={onPreviewProblem}>Preview</button>}
              <button className="btn btn-plain btn-sm" type="button" onClick={onOpenConfigs}><Icon name="folder" size={14} />Configs</button>
              <button className="btn btn-tinted btn-sm" type="button" onClick={onEditProblem}><Icon name="edit" size={14} />Edit</button>
            </span>
          </div>
          <div className="group">
            <div className="row"><span className="row-label"><span>Trucks</span></span><span className="row-value">{problem.trucks.length}</span></div>
            <div className="row"><span className="row-label"><span>Packages</span></span><span className="row-value">{problem.packages.length}</span></div>
            <div className="row"><span className="row-label"><span>Total value</span></span><span className="row-value">{formatNumber(totalValue)}</span></div>
            <div className="row">
              <span className="row-label"><span>Total weight</span><small>Fleet capacity {formatWhole(capacity)} kg</small></span>
              <span className="row-value">{formatNumber(totalWeight)} kg</span>
            </div>
          </div>
        </section>

        <section>
          <div className="section-title"><span>Algorithm</span></div>
          <Segmented label="Algorithm" options={ALGORITHMS} value={algorithm} onChange={(value) => { setAlgorithm(value); setInvalid([]) }} />
          {algorithm === 'hill_climbing' && (
            <div className="pills" role="group" aria-label="Hill Climbing variant">
              {VARIANTS.map((value) => (
                <button key={value} className="pill-opt" type="button" aria-pressed={variant === value} onClick={() => setVariant(value)}>{VARIANT_LABELS[value]}</button>
              ))}
            </div>
          )}
        </section>

        <section>
          <div className="section-title"><span>Objective</span></div>
          <Segmented<ObjectiveMode> label="Objective" options={OBJECTIVES} value={objective} onChange={setObjective} />
          <p className="caption">{OBJECTIVE_HELP[objective]}</p>
        </section>

        <section>
          <div className="section-title"><span>Parameters</span></div>
          {!limits ? (
            <div className="group empty-state">
              {limitsError ? (
                <>
                  <p>{limitsError}</p>
                  <button className="btn btn-plain btn-sm" type="button" onClick={onRetryLimits}><Icon name="refresh" size={14} />Try again</button>
                </>
              ) : <p><span className="spinner" aria-hidden="true" /> Loading allowed ranges from the backend</p>}
            </div>
          ) : (
            <div className="group">
              {fields.map((field) => {
                const range = limits.parameters[algorithm][field.key]
                const step = range.integer ? 1 : field.step ?? 0.01
                const auto = range.nullable && (drafts[field.key] ?? '') === ''
                const id = `param-${algorithm}-${field.key}`
                const allowed = describeRange(range)
                const hint = field.hint ? `${field.hint}, ${allowed.charAt(0).toLowerCase()}${allowed.slice(1)}` : `Allowed ${allowed.charAt(0).toLowerCase()}${allowed.slice(1)}`
                return (
                  <div className="row param-row" key={field.key}>
                    <div className="row-label"><label htmlFor={id}>{field.label}</label><small id={`${id}-hint`}>{hint}</small></div>
                    <div className="param-controls">
                      {range.nullable && (
                        <button className="pill-opt" type="button" aria-pressed={auto} onClick={() => setDraft(field.key, auto ? String(Math.max(Number(meanValue.toFixed(2)), 1)) : '')}>Auto</button>
                      )}
                      <NumberField
                        id={id}
                        label={field.label}
                        value={drafts[field.key] ?? ''}
                        onChange={(value) => setDraft(field.key, value)}
                        step={step}
                        integer={range.integer}
                        min={lowestValue(range, step)}
                        max={highestValue(range, step)}
                        disabled={auto}
                        placeholder={auto ? 'Auto' : undefined}
                        invalid={invalid.includes(field.key)}
                        describedBy={`${id}-hint`}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
          <p className="caption">Allowed ranges come from the backend, so the form always matches what the server accepts.</p>
        </section>

        <section>
          <div className="section-title"><span>Seed</span></div>
          <div className="group seed-row">
            <input
              className={invalid.includes('seed') ? 'seed-input invalid' : 'seed-input'}
              type="text"
              inputMode="numeric"
              value={seedText}
              aria-label="Seed"
              aria-invalid={invalid.includes('seed') || undefined}
              onChange={(event) => {
                setSeedText(event.currentTarget.value)
                setInvalid((keys) => keys.filter((key) => key !== 'seed'))
                clearErrorToast()
              }}
            />
            {OFFICIAL_SEEDS.map((seed) => (
              <button key={seed} className="pill-opt" type="button" aria-pressed={seedText === String(seed)} onClick={() => setSeedText(String(seed))}>{seed}</button>
            ))}
            <button className="icon-btn" type="button" aria-label="Random seed" title="Random seed" onClick={() => setSeedText(String(Math.floor(Math.random() * 100_000)))}><Icon name="dice" size={18} /></button>
          </div>
          <p className="caption">The official experiment seeds are 42, 123, and 2026.</p>
        </section>

        <section>
          <div className="section-title"><span>Run options</span></div>
          <div className="group">
            <div className="row">
              <div className="row-label"><label htmlFor="opt-persist">Save run</label><small>Off by default; enable to save this run</small></div>
              <GlassSwitch id="opt-persist" checked={persist} onChange={setPersist} />
            </div>
            <div className="row">
              <div className="row-label"><label htmlFor="opt-replay">Record replay</label><small>Stores the state of every step for playback</small></div>
              <GlassSwitch id="opt-replay" checked={recordReplay} onChange={setRecordReplay} />
            </div>
          </div>
        </section>
      </div>
      <div className="panel-foot">
        <button className="btn btn-primary btn-lg" type="button" disabled={!limits || running} onClick={run}>
          {running ? <span className="spinner light" aria-hidden="true" /> : <Icon name="play" size={18} />}
          {running ? 'Running' : `Run ${ALGORITHM_LABELS[algorithm]}`}
        </button>
      </div>
    </aside>
  )
}
