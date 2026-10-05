import assert from 'node:assert/strict'
import test from 'node:test'
import { isExperimentResult } from './validation'

function resultWith(placement: unknown) {
  return {
    id: 'contract-test', algorithm: 'hill_climbing', seed: 42,
    initial_state: { placements: [placement] }, final_state: { placements: [] },
    initial_score: 0, final_score: 0, runtime_ms: 0, iterations: 0,
    history: [], metadata: {},
  }
}

test('accepts outside and loaded placements with all six numeric orientations', () => {
  for (const orientation of [0, 1, 2, 3, 4, 5]) {
    assert.equal(isExperimentResult(resultWith({
      package_id: 'P1', truck_id: null, position: null, orientation,
    })), true)
    assert.equal(isExperimentResult(resultWith({
      package_id: 'P1', truck_id: 'T1', position: { x: -1, y: 2, z: 3 }, orientation,
    })), true)
  }
})

test('rejects malformed placements and inconsistent assignments', () => {
  const outside = { package_id: 'P1', truck_id: null, position: null, orientation: 0 }
  for (const placement of [
    null, {}, { ...outside, package_id: 1 },
    { ...outside, truck_id: 'T1' },
    { ...outside, position: { x: 0, y: 0, z: 0 } },
    { ...outside, truck_id: 1 },
    { ...outside, orientation: 'horizontal' },
    { ...outside, orientation: -1 }, { ...outside, orientation: 6 },
    { ...outside, orientation: 0.5 },
    { ...outside, truck_id: 'T1', position: { x: 0.5, y: 0, z: 0 } },
    { ...outside, truck_id: 'T1', position: { x: NaN, y: 0, z: 0 } },
    { ...outside, truck_id: 'T1', position: { x: 0, y: 0 } },
  ]) {
    assert.equal(isExperimentResult(resultWith(placement)), false)
  }
})
