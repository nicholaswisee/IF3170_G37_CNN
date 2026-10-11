import assert from 'node:assert/strict'
import test from 'node:test'
import { progressLabelForAlgorithm, toObjectiveChartData } from './objectiveChartData'
import type { SearchEvent } from '../types/experiment'

function event(iteration: number, current_score: number, mean_score: number | null): SearchEvent {
  return {
    iteration, current_score, best_score: current_score, candidate_score: null, mean_score,
    accepted: null, move: null, temperature: null, acceptance_probability: null,
    state_snapshot: null, metadata: {},
  }
}

test('maps GA generation maximum and mean scores independently', () => {
  assert.deepEqual(toObjectiveChartData([event(0, 8, 3), event(1, 10, 7)], 'genetic_algorithm'), [
    { generation: 0, maximum: 8, mean: 3 }, { generation: 1, maximum: 10, mean: 7 },
  ])
})

test('keeps HC maximum objective trace and safely maps null means', () => {
  assert.deepEqual(toObjectiveChartData([event(0, 4, null), event(1, 6, null)], 'hill_climbing'), [
    { generation: 0, maximum: 4, mean: null }, { generation: 1, maximum: 6, mean: null },
  ])
})

test('uses generation terminology only for GA', () => {
  assert.equal(progressLabelForAlgorithm('genetic_algorithm'), 'Generation')
  assert.equal(progressLabelForAlgorithm('hill_climbing'), 'Iteration')
  assert.equal(progressLabelForAlgorithm(null), 'Iteration')
})
