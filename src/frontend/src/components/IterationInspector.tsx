import { useReplayStore } from '../stores/replayStore'
import { progressLabelForAlgorithm } from './objectiveChartData'

export function IterationInspector() {
  const { currentIteration, experiment } = useReplayStore()
  const event = experiment?.history[currentIteration]
  const source = !experiment ? 'Configured problem preview' : experiment.metadata.placeholder === true ? 'Placeholder (not optimized)' : 'Backend run'
  const progressLabel = progressLabelForAlgorithm(experiment?.algorithm)
  const objectiveMode = experiment?.objective_mode === 'eta_weighted_value' ? 'ETA-weighted value' : experiment ? 'Total value' : '—'

  return (
    <section className="inspector" aria-labelledby="inspector-heading">
      <div className="panel-heading">
          <span className="panel-index">02</span>
          <h2 id="inspector-heading">{progressLabel} inspector</h2>
      </div>
      <dl>
        <div><dt>Source</dt><dd>{source}</dd></div>
        <div><dt>{progressLabel}</dt><dd>{event?.iteration ?? '—'}</dd></div>
        <div><dt>Objective</dt><dd>{event?.current_score ?? experiment?.final_score ?? '—'}</dd></div>
        <div><dt>Objective mode</dt><dd>{objectiveMode}</dd></div>
        <div><dt>Move</dt><dd>{event?.move?.type ?? '—'}</dd></div>
        <div><dt>Decision</dt><dd>{event?.accepted == null ? '—' : event.accepted ? 'Accepted' : 'Rejected'}</dd></div>
        {experiment?.algorithm === 'simulated_annealing' && (
          <>
            <div><dt>Best objective</dt><dd>{event?.best_score ?? experiment.best_score}</dd></div>
            <div><dt>Temperature</dt><dd>{event?.temperature ?? '—'}</dd></div>
            <div><dt>Acceptance probability</dt><dd>{event?.acceptance_probability ?? '—'}</dd></div>
          </>
        )}
      </dl>
    </section>
  )
}
