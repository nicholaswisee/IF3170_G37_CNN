import assert from 'node:assert/strict'
import test from 'node:test'
import type { SearchEvent } from '../types/experiment'
import { bestEventIndex, bestScorePerRestart, progressLabel, restartStarts, toAnnealingSeries, toObjectiveSeries } from './chartData'

function event(iteration: number, current_score: number, extra: Partial<SearchEvent> = {}): SearchEvent {
  return {
    iteration, current_score, best_score: current_score, candidate_score: null, mean_score: null,
    accepted: null, move: null, temperature: null, acceptance_probability: null,
    state_snapshot: null, metadata: {}, ...extra,
  }
}

test('every algorithm uses the iteration key for chart data', () => {
  assert.deepEqual(toObjectiveSeries([event(0, 8, { mean_score: 3 }), event(1, 10, { mean_score: 7, best_score: 10 })]), [
    { iteration: 0, current: 8, best: 8, mean: 3 },
    { iteration: 1, current: 10, best: 10, mean: 7 },
  ])
  assert.deepEqual(toObjectiveSeries([event(0, 4)])[0].mean, null)
})

test('annealing series keeps temperature and acceptance probability per iteration', () => {
  assert.deepEqual(toAnnealingSeries([event(0, 1, { temperature: 50 }), event(1, 1, { temperature: 49, acceptance_probability: 0.4 })]), [
    { iteration: 0, temperature: 50, probability: null },
    { iteration: 1, temperature: 49, probability: 0.4 },
  ])
})

test('labels generations only for GA', () => {
  assert.equal(progressLabel('genetic_algorithm'), 'Generation')
  assert.equal(progressLabel('hill_climbing'), 'Iteration')
  assert.equal(progressLabel('simulated_annealing'), 'Iteration')
  assert.equal(progressLabel(null), 'Iteration')
})

test('finds where each random restart climb begins and its best score', () => {
  const history = [0, 0, 1, 1, 1, 2].map((restart, index) => event(index, index, { metadata: { restart } }))
  assert.deepEqual(restartStarts(history), [2, 5])
  assert.deepEqual(restartStarts([event(0, 1), event(1, 2)]), [])
  assert.deepEqual(bestScorePerRestart({ best_score_per_restart: [10, 'x', 12] }), [{ restart: 1, score: 10 }, { restart: 3, score: 12 }])
  assert.deepEqual(bestScorePerRestart({}), [])
})

test('best view points at the first event that reached the best score', () => {
  const history = [event(0, 1), event(1, 5), event(2, 5), event(3, 4)]
  assert.equal(bestEventIndex(history, 5), 1)
  assert.equal(bestEventIndex(history, 99), 3)
  assert.equal(bestEventIndex([], 1), 0)
})
