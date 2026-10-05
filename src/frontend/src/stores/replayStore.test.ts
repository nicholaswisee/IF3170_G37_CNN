import assert from 'node:assert/strict'
import test from 'node:test'
import { selectReplayState } from './replayStore'
import type { ExperimentResult, OptimizationState } from '../types/experiment'

const best: OptimizationState = { placements: [] }
const first: OptimizationState = { placements: [{ package_id: 'a', truck_id: null, position: null, orientation: 0 }] }
const second: OptimizationState = { placements: [{ package_id: 'b', truck_id: null, position: null, orientation: 0 }] }
const experiment = {
  best_state: best,
  history: [{ state_snapshot: first }, { state_snapshot: second }],
} as ExperimentResult
const withoutSnapshot = {
  ...experiment,
  history: [{ ...experiment.history[0], state_snapshot: null }],
} as ExperimentResult

test('selects the current iteration snapshot and falls back to best state', () => {
  assert.equal(selectReplayState(experiment, 0), first)
  assert.equal(selectReplayState(experiment, 1), second)
  assert.equal(selectReplayState(withoutSnapshot, 0), best)
})

test('falls back to best state for empty history and to null without an experiment', () => {
  assert.equal(selectReplayState({ ...experiment, history: [] }, 0), best)
  assert.equal(selectReplayState(null, 0), null)
})
