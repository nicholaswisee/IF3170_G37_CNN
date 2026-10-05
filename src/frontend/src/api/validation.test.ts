import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'
import { isExperimentResult } from './validation'
import type { ExperimentResult } from '../types/experiment'

function readFixture(): ExperimentResult {
  const value: unknown = JSON.parse(readFileSync(resolve(process.cwd(), '../backend/tests/fixtures/experiment_result.json'), 'utf8'))
  assert.ok(isExperimentResult(value), 'backend fixture must satisfy the frontend contract')
  return value
}

const fixture = readFixture()

function resultWith(placement: unknown) {
  return { ...fixture, initial_state: { placements: [placement] } }
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

test('accepts the complete backend experiment fixture', () => {
  assert.equal(isExperimentResult(fixture), true)
})

test('requires best state and final and best scores', () => {
  for (const key of ['best_state', 'final_score', 'best_score']) {
    const incomplete: Record<string, unknown> = { ...fixture }
    delete incomplete[key]
    assert.equal(isExperimentResult(incomplete), false, `accepts result without ${key}`)
  }
})

test('rejects nonfinite package value, package weight, and truck capacity', () => {
  for (const field of ['value', 'weight'] as const) {
    for (const number of [NaN, Infinity, -Infinity]) {
      const invalid = structuredClone(fixture)
      invalid.problem.packages[0][field] = number
      assert.equal(isExperimentResult(invalid), false)
    }
  }
  for (const number of [NaN, Infinity, -Infinity]) {
    const invalid = structuredClone(fixture)
    invalid.problem.trucks[0].max_capacity = number
    assert.equal(isExperimentResult(invalid), false)
  }
})

test('rejects nonfinite required result and optional event metrics', () => {
  for (const field of ['seed', 'initial_score', 'final_score', 'best_score', 'runtime_ms', 'iterations']) {
    for (const number of [NaN, Infinity, -Infinity]) {
      assert.equal(isExperimentResult({ ...fixture, [field]: number }), false, `accepts nonfinite ${field}`)
    }
  }
  for (const field of ['candidate_score', 'mean_score', 'temperature', 'acceptance_probability']) {
    for (const number of [NaN, Infinity, -Infinity]) {
      const event = {
        iteration: 0, current_score: 0, best_score: 0, candidate_score: null, mean_score: null,
        accepted: null, move: null, temperature: null, acceptance_probability: null,
        state_snapshot: null, metadata: {}, [field]: number,
      }
      assert.equal(isExperimentResult({ ...fixture, history: [event] }), false, `accepts nonfinite ${field}`)
    }
  }
})
