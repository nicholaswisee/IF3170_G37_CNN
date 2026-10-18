import assert from 'node:assert/strict'
import test from 'node:test'
import type { Problem } from '../types/experiment'
import { createProblemForm, parseProblemForm, problemFormReducer } from './problemForm'

const problem: Problem = {
  trucks: [{ id: 'T1', width: 4, length: 5, height: 3, max_capacity: 40 }],
  packages: [{ id: 'P1', width: 1, length: 2, height: 1, value: 7.5, weight: 2, eta: 1, is_fragile: true }],
}

test('a problem survives the round trip through the editor drafts', () => {
  assert.deepEqual(parseProblemForm(createProblemForm(problem)).problem, problem)
})

test('adding rows creates unique IDs and the last truck cannot be removed', () => {
  let state = createProblemForm(problem)
  state = problemFormReducer(state, { type: 'add-truck' })
  state = problemFormReducer(state, { type: 'add-package' })
  assert.deepEqual(state.trucks.map((row) => row.values.id), ['T1', 'truck-1'])
  assert.deepEqual(state.packages.map((row) => row.values.id), ['P1', 'package-1'])
  const single = createProblemForm(problem)
  assert.equal(problemFormReducer(single, { type: 'remove-truck', key: single.trucks[0].key }), single)
})

test('reports field errors by path for empty, fractional, negative, and duplicate values', () => {
  let state = createProblemForm(problem)
  const truckKey = state.trucks[0].key
  const packageKey = state.packages[0].key
  state = problemFormReducer(state, { type: 'update-truck', key: truckKey, changes: { width: '2.5', max_capacity: '-1' } })
  state = problemFormReducer(state, { type: 'update-package', key: packageKey, changes: { eta: '', id: 'T1' } })
  state = problemFormReducer(state, { type: 'add-package' })
  state = problemFormReducer(state, { type: 'update-package', key: state.packages[1].key, changes: { id: 'T1' } })
  const { problem: parsed, errors } = parseProblemForm(state)
  assert.equal(parsed, null)
  assert.ok(errors[`trucks.${truckKey}.width`])
  assert.ok(errors[`trucks.${truckKey}.max_capacity`])
  assert.ok(errors[`packages.${packageKey}.eta`])
  assert.ok(errors[`packages.${packageKey}.id`], 'duplicate package IDs are flagged')
})
