import { useReplayStore } from '../stores/replayStore'

export function IterationInspector() {
  const { currentIteration, experiment } = useReplayStore()
  const event = experiment?.history[currentIteration]
  const source = !experiment ? 'Preview fixture' : experiment.metadata.placeholder === true ? 'Placeholder (not optimized)' : 'Backend run'

  return (
    <section className="inspector" aria-labelledby="inspector-heading">
      <div className="panel-heading">
        <span className="panel-index">02</span>
        <h2 id="inspector-heading">Iteration inspector</h2>
      </div>
      <dl>
        <div><dt>Source</dt><dd>{source}</dd></div>
        <div><dt>Iteration</dt><dd>{event?.iteration ?? '—'}</dd></div>
        <div><dt>Objective</dt><dd>{event?.current_score ?? experiment?.final_score ?? '—'}</dd></div>
        <div><dt>Move</dt><dd>{event?.move?.type ?? '—'}</dd></div>
        <div><dt>Decision</dt><dd>{event?.accepted == null ? '—' : event.accepted ? 'Accepted' : 'Rejected'}</dd></div>
      </dl>
    </section>
  )
}
