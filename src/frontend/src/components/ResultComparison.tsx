import type { ExperimentResult } from '../types/experiment'

const algorithmLabels: Record<ExperimentResult['algorithm'], string> = {
  hill_climbing: 'Hill Climbing',
  simulated_annealing: 'Simulated Annealing',
  genetic_algorithm: 'Genetic Algorithm',
}

const objectiveLabels: Record<ExperimentResult['objective_mode'], string> = {
  total_value: 'Total value',
  eta_weighted_value: 'ETA-weighted value',
}

function loadedCount(state: ExperimentResult['best_state']): number {
  return state.placements.filter((placement) => placement.truck_id !== null).length
}

function formatScore(score: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(score)
}

export function ResultSummary({ experiment }: { experiment: ExperimentResult | null }) {
  return (
    <section className="result-summary" aria-labelledby="summary-heading">
      <div className="panel-heading">
        <span className="panel-index">04</span>
        <h2 id="summary-heading">Active run summary</h2>
      </div>
      {!experiment ? <p className="comparison-empty">Select or run an experiment to see its results.</p> : (
        <>
          <p className="summary-context">{algorithmLabels[experiment.algorithm]} · {objectiveLabels[experiment.objective_mode]} · seed {experiment.seed}</p>
          <dl className="summary-metrics">
            <div><dt>Initial</dt><dd>{formatScore(experiment.initial_score)} · {loadedCount(experiment.initial_state)} loaded</dd></div>
            <div><dt>Final</dt><dd>{formatScore(experiment.final_score)} · {loadedCount(experiment.final_state)} loaded</dd></div>
            <div><dt>Best</dt><dd>{formatScore(experiment.best_score)} · {loadedCount(experiment.best_state)} loaded</dd></div>
            <div><dt>Runtime</dt><dd>{formatScore(experiment.runtime_ms)} ms</dd></div>
            {experiment.algorithm === 'simulated_annealing' && (
              <>
                <div><dt>Iterations</dt><dd>{experiment.iterations}</dd></div>
                <div><dt>Stuck events</dt><dd>{typeof experiment.metadata.stuck_events === 'number' ? experiment.metadata.stuck_events : '—'}</dd></div>
              </>
            )}
          </dl>
        </>
      )}
    </section>
  )
}

export function RunSelector({
  experiments,
  selectedId,
  onSelect,
}: {
  experiments: ExperimentResult[]
  selectedId: string
  onSelect: (experiment: ExperimentResult) => void
}) {
  return (
    <label className="field-label run-selector" htmlFor="run-selector">
      Active replay
      <select
        id="run-selector"
        value={selectedId}
        disabled={experiments.length === 0}
        onChange={(event) => {
          const selected = experiments.find((experiment) => experiment.id === event.currentTarget.value)
          if (selected) onSelect(selected)
        }}
      >
        {experiments.length === 0 && <option value="">No runs available</option>}
        {experiments.length > 0 && selectedId === '' && <option value="">Configured problem preview</option>}
        {experiments.map((experiment, index) => (
          <option key={experiment.id} value={experiment.id}>
            {index + 1}. {algorithmLabels[experiment.algorithm]} · {experiment.id.slice(0, 8)}
          </option>
        ))}
      </select>
    </label>
  )
}

export function ExperimentComparisonTable({
  experiments,
  selectedId,
  onSelect,
}: {
  experiments: ExperimentResult[]
  selectedId: string
  onSelect: (experiment: ExperimentResult) => void
}) {
  return (
    <section className="comparison-panel" aria-labelledby="comparison-heading">
      <div className="panel-heading">
        <span className="panel-index">05</span>
        <h2 id="comparison-heading">Experiment comparison</h2>
      </div>
      {experiments.length === 0 ? <p className="comparison-empty">No saved or local runs yet.</p> : (
        <div className="comparison-table-wrap" role="region" aria-label="Experiment comparison table" tabIndex={0}>
          <table className="comparison-table">
            <thead>
              <tr><th scope="col">Run</th><th scope="col">Algorithm / variant</th><th scope="col">Objective</th><th scope="col">Seed</th><th scope="col">Parameters</th><th scope="col">Best score</th><th scope="col">Runtime</th></tr>
            </thead>
            <tbody>
              {experiments.map((experiment, index) => (
                <tr key={experiment.id} aria-selected={selectedId === experiment.id}>
                  <td><button className="comparison-run" type="button" aria-label={`Replay run ${index + 1}`} onClick={() => onSelect(experiment)}>{index + 1}</button></td>
                  <td>{algorithmLabels[experiment.algorithm]}{experiment.variant ? ` / ${experiment.variant.replaceAll('_', ' ')}` : ''}</td>
                  <td>{objectiveLabels[experiment.objective_mode]}</td>
                  <td>{experiment.seed}</td>
                  <td><code>{JSON.stringify(experiment.parameters)}</code></td>
                  <td>{formatScore(experiment.best_score)}</td>
                  <td>{formatScore(experiment.runtime_ms)} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
