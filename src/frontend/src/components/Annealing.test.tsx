import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { renderToStaticMarkup } from 'react-dom/server'
import { AnnealingParameters } from './AnnealingParameters'
import { AnnealingCharts } from './AnnealingCharts'
import { toAnnealingChartData } from './annealingChartData'
import { ResultSummary } from './ResultComparison'
import { isExperimentResult } from '../api/validation'
import { selectReplayState, useReplayStore } from '../stores/replayStore'
import type { ExperimentResult, SearchEvent } from '../types/experiment'

const fixture: unknown = JSON.parse(readFileSync(resolve(process.cwd(), '../backend/tests/fixtures/experiment_result.json'), 'utf8'))
assert.ok(isExperimentResult(fixture))

function event(iteration: number, current: number, best: number, probability: number | null): SearchEvent {
  return { iteration, current_score: current, best_score: best, candidate_score: null,
    mean_score: null, accepted: probability === null ? null : false, move: null,
    temperature: 10 / (iteration + 1), acceptance_probability: probability,
    state_snapshot: null, metadata: {} }
}

test('SA charts keep current and best scores separate and preserve missing probabilities', () => {
  const history = [event(0, 10, 10, null), event(1, 5, 10, 0.3), event(2, 5, 10, 0)]
  assert.deepEqual(toAnnealingChartData(history), [
    { iteration: 0, current: 10, best: 10, temperature: 10, probability: null },
    { iteration: 1, current: 5, best: 10, temperature: 5, probability: 0.3 },
    { iteration: 2, current: 5, best: 10, temperature: 10 / 3, probability: 0 },
  ])
  const markup = renderToStaticMarkup(<AnnealingCharts history={history} />)
  for (const label of ['Current and best objective', 'Temperature', 'Acceptance probability']) assert.ok(markup.includes(label))
  assert.deepEqual(toAnnealingChartData([]), [])
  assert.match(renderToStaticMarkup(<AnnealingCharts history={[]} />), /This run recorded no history/)
})

test('SA controls expose editable values and optional automatic initial temperature', () => {
  const markup = renderToStaticMarkup(<AnnealingParameters values={{ initial_temperature: '', alpha: '0.995', min_temperature: '0.001', max_iterations: '5000', stuck_patience: '50' }} onChange={() => {}} />)
  assert.match(markup, /placeholder="Automatic"/)
  const inputs = markup.match(/<input[^>]+>/g) ?? []
  assert.equal(inputs.length, 5)
  assert.ok(!inputs[0].includes('required'))
  assert.ok(inputs.slice(1).every((input) => input.includes('required')))
  assert.match(markup, /max="5000"/)
})

test('SA summary and replay preserve best state when current score declines', () => {
  const initial = fixture.initial_state
  const best = fixture.best_state
  const current = structuredClone(initial)
  const run: ExperimentResult = { ...fixture, algorithm: 'simulated_annealing', variant: null,
    best_score: 10, final_score: 5, best_state: best, final_state: current, iterations: 2,
    metadata: { stuck_events: 0 }, history: [
      { ...event(0, 0, 0, null), state_snapshot: initial },
      { ...event(1, 10, 10, 1), state_snapshot: best },
      { ...event(2, 5, 10, 0.3), state_snapshot: current },
    ] }
  const markup = renderToStaticMarkup(<ResultSummary experiment={run} />)
  assert.match(markup, /Iterations<\/dt><dd>2/)
  assert.match(markup, /Stuck events<\/dt><dd>0/)
  assert.match(markup, /Best/)
  assert.match(markup, /Runtime/)
  const store = useReplayStore.getState()
  store.reset()
  store.setExperiment(run)
  store.setIteration(2)
  assert.equal(selectReplayState(useReplayStore.getState().experiment, 2), current)
  assert.equal(selectReplayState({ ...run, history: run.history.map((item) => ({ ...item, state_snapshot: null })) }, 2), best)
  store.reset()
})
