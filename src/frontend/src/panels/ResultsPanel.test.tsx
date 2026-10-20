import assert from 'node:assert/strict'
import test from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { readExperimentFixture } from '../testing/fixtures'
import type { ExperimentResult, Problem, SearchEvent } from '../types/experiment'
import { OutsideTab, ResultsPanel, StepTab, SummaryTab } from './ResultsPanel'
import { runMetrics } from './runMetrics'

const fixture = readExperimentFixture()

const problem: Problem = {
  trucks: [{ id: 'T1', width: 4, length: 4, height: 4, max_capacity: 10 }],
  packages: [
    { id: 'P1', width: 2, length: 3, height: 1, value: 15, weight: 4, is_fragile: true, eta: 2 },
    { id: 'P2', width: 1, length: 1, height: 1, value: 5, weight: 1, is_fragile: false, eta: 0 },
  ],
}
const state = {
  placements: [
    { package_id: 'P1', truck_id: null, position: null, orientation: 0 as const },
    { package_id: 'P2', truck_id: 'T1', position: { x: 0, y: 0, z: 0 }, orientation: 0 as const },
  ],
}

test('summary shows the three scores, run metrics, and the fleet load of the shown state', () => {
  const markup = renderToStaticMarkup(<SummaryTab experiment={fixture} problem={problem} state={state} viewCaption="Iteration 3" />)
  for (const label of ['Initial', 'Final', 'Best', 'Runtime', 'Stopped because', 'Fleet load', 'Iteration 3']) assert.ok(markup.includes(label), label)
  assert.match(markup, /1 of 10 kg, 1 loaded/)
})

test('summary without a run explains how to get results and still shows the fleet', () => {
  const markup = renderToStaticMarkup(<SummaryTab experiment={null} problem={problem} state={state} viewCaption="Preview" />)
  assert.match(markup, /Run an algorithm or open a saved run/)
  assert.match(markup, /T1/)
})

test('run metrics read algorithm metadata by name', () => {
  const run: ExperimentResult = {
    ...fixture,
    algorithm: 'simulated_annealing',
    runtime_ms: 1234,
    iterations: 500,
    metadata: { termination_reason: 'temperature_minimum', stuck_events: 3, final_temperature: 0.00099, persisted: true },
  }
  assert.deepEqual(runMetrics(run), [
    ['Runtime', '1,234 ms'],
    ['Iterations', '500'],
    ['Stopped because', 'Temperature minimum'],
    ['Stuck events', '3'],
    ['Final temperature', '0.00099'],
    ['Saved to output', 'Yes'],
  ])
  const ga = runMetrics({ ...fixture, algorithm: 'genetic_algorithm', metadata: { population_size: 50 } })
  assert.equal(ga[1][0], 'Generations')
  assert.deepEqual(ga.at(-1), ['Population size', '50'])
})

test('outside tab lists every outside package with the fields the freeze requires', () => {
  const markup = renderToStaticMarkup(<OutsideTab problem={problem} state={state} colorMode="identity" onSelect={() => {}} />)
  assert.match(markup, /P1/)
  assert.match(markup, /2 × 3 × 1, value 15, 4 kg, ETA 2, WLH/)
  assert.match(markup, /Fragile/)
  assert.doesNotMatch(markup, />P2</)
  const loaded = renderToStaticMarkup(<OutsideTab problem={problem} state={{ placements: [state.placements[1]] }} colorMode="identity" onSelect={() => {}} />)
  assert.doesNotMatch(loaded, /Every package is loaded/, 'a package missing from the state still counts as outside')
})

test('step tab describes the move of the shown event in plain words', () => {
  const move = {
    type: 'RELOCATE' as const,
    package_ids: ['P1'],
    before: [{ package_id: 'P1', truck_id: 'T1', position: { x: 0, y: 0, z: 0 }, orientation: 0 as const }],
    after: [{ package_id: 'P1', truck_id: 'T2', position: { x: 1, y: 2, z: 0 }, orientation: 0 as const }],
    metadata: {},
  }
  const start: SearchEvent = {
    iteration: 0, current_score: 10, best_score: 10, candidate_score: null, mean_score: null, accepted: null,
    move: null, temperature: 13, acceptance_probability: null, state_snapshot: null, metadata: {},
  }
  const event: SearchEvent = { ...start, iteration: 4, move, accepted: true, candidate_score: 30, current_score: 30, temperature: 12.5, acceptance_probability: 1 }
  const run = { ...fixture, algorithm: 'simulated_annealing' as const, history: [start, event] }
  const markup = renderToStaticMarkup(<StepTab experiment={run} event={event} index={1} onJump={() => {}} />)
  assert.match(markup, /P1 transferred from T1 to T2/)
  assert.match(markup, /Accepted/)
  assert.match(markup, /To T2 at \(1, 2, 0\), WLH/)
  assert.match(markup, /Acceptance probability/)
  assert.match(markup, /T1 to T2/)
})

test('fallback notices appear only in their corresponding Replay and Final views', () => {
  const fallbackEvent: SearchEvent = { ...fixture.history[0], metadata: { feasible_fallback: true } }
  const run: ExperimentResult = { ...fixture, algorithm: 'genetic_algorithm', history: [fallbackEvent], metadata: { final_state_fallback: true } }
  const render = (stateView: 'replay' | 'initial' | 'final' | 'best', shownEvent: SearchEvent | null) => renderToStaticMarkup(
    <ResultsPanel open={true} experiment={run} problem={problem} state={shownEvent?.state_snapshot ?? state} shownEvent={shownEvent} shownIndex={0} stateView={stateView} colorMode="identity" onClose={() => {}} onJump={() => {}} onSelectPackage={() => {}} onExpandCharts={() => {}} />,
  )
  const replay = render('replay', fallbackEvent)
  assert.match(replay, /feasible solution from an earlier generation/)
  assert.doesNotMatch(replay, /final population/)
  assert.doesNotMatch(render('initial', null), /earlier generation|final population/)
  assert.match(render('final', null), /final population had no feasible individual/)
  assert.doesNotMatch(render('best', null), /earlier generation|final population/)
})

test('GA step details separate raw current objective from normalized fitness and avoid archive claims', () => {
  const event: SearchEvent = { ...fixture.history[0], current_score: 42, best_score: 55, mean_score: 0.5, temperature: null, acceptance_probability: null, metadata: { max_fitness: 1.25 } }
  const run: ExperimentResult = { ...fixture, algorithm: 'genetic_algorithm', history: [event] }
  const markup = renderToStaticMarkup(<StepTab experiment={run} event={event} index={0} onJump={() => {}} />)
  assert.match(markup, /Current objective/)
  assert.match(markup, /Max fitness/)
  assert.match(markup, /Mean fitness/)
  assert.match(markup, /Best objective/)
  assert.doesNotMatch(markup, /Best individual of generation/)
})
