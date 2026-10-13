import assert from 'node:assert/strict'
import test from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { mockProblem } from '../mocks/fleetFixture'
import type { Problem } from '../types/experiment'
import { ProblemConfiguration } from './ProblemConfiguration'
import { createProblemForm, parseProblemForm, problemFormReducer, type PackageDraft, type TruckDraft } from './problemForm'

const singleTruck: Problem = {
  trucks: [{ id: 'truck-1', width: 2, length: 3, height: 4, max_capacity: 12.5 }],
  packages: [{ id: 'package-1', width: 1, length: 2, height: 3, value: 2.5, weight: 0.5, eta: 0, is_fragile: true }],
}

test('form conversion preserves every single and multi-truck problem field', () => {
  for (const problem of [singleTruck, mockProblem]) {
    const result = parseProblemForm(createProblemForm(problem))
    assert.deepEqual(result, { problem, errors: {} })
    assert.notEqual(result.problem, problem)
    assert.notEqual(result.problem?.trucks[0], problem.trucks[0])
  }
})

test('editing, adding and removing rows keeps stable keys and leaves the original problem intact', () => {
  const original = structuredClone(singleTruck)
  let draft = createProblemForm(singleTruck)
  const firstKey = draft.trucks[0].key
  draft = problemFormReducer(draft, { type: 'update-truck', key: firstKey, changes: { id: 'truck-2', width: '8', max_capacity: '50.5' } })
  draft = problemFormReducer(draft, { type: 'add-truck' })
  assert.equal(draft.trucks[0].key, firstKey)
  assert.equal(draft.trucks[1].values.id, 'truck-1')
  draft = problemFormReducer(draft, { type: 'add-truck' })
  assert.equal(draft.trucks[2].values.id, 'truck-3')
  draft = problemFormReducer(draft, { type: 'add-package' })
  const addedPackage = draft.packages[1]
  assert.equal(addedPackage.values.id, 'package-2')
  draft = problemFormReducer(draft, { type: 'update-package', key: addedPackage.key, changes: { id: 'custom', value: '3.25', weight: '1.5', eta: '5', is_fragile: true } })
  draft = problemFormReducer(draft, { type: 'remove-package', key: draft.packages[0].key })
  assert.equal(draft.packages[0].key, addedPackage.key)
  draft = problemFormReducer(draft, { type: 'remove-truck', key: draft.trucks[1].key })
  const result = parseProblemForm(draft)
  assert.ok(result.problem)
  assert.equal(result.problem.trucks.length, 2)
  assert.deepEqual(result.problem.trucks[0], { id: 'truck-2', width: 8, length: 3, height: 4, max_capacity: 50.5 })
  assert.deepEqual(result.problem.packages[0], { id: 'custom', width: 1, length: 1, height: 1, value: 3.25, weight: 1.5, eta: 5, is_fragile: true })
  assert.deepEqual(singleTruck, original)
  const keys = [...draft.trucks, ...draft.packages].map((row) => row.key)
  assert.equal(new Set(keys).size, keys.length)
})

test('the last truck cannot be removed but all packages can be removed', () => {
  let draft = createProblemForm(singleTruck)
  assert.equal(problemFormReducer(draft, { type: 'remove-truck', key: draft.trucks[0].key }), draft)
  draft = problemFormReducer(draft, { type: 'remove-package', key: draft.packages[0].key })
  assert.deepEqual(parseProblemForm(draft).problem, { trucks: singleTruck.trucks, packages: [] })
  assert.equal(parseProblemForm({ ...draft, trucks: [] }).problem, null)
  assert.equal(parseProblemForm({ ...draft, trucks: [] }).errors.trucks, 'At least one truck is required.')
})

test('IDs are trimmed and unique within each list while truck and package IDs may coincide', () => {
  let draft = createProblemForm(singleTruck)
  draft.trucks[0].values.id = ' shared '
  draft.packages[0].values.id = 'shared'
  assert.equal(parseProblemForm(draft).problem?.trucks[0].id, 'shared')
  draft = problemFormReducer(draft, { type: 'add-truck' })
  draft = problemFormReducer(draft, { type: 'add-package' })
  draft.trucks[1].values.id = 'shared'
  draft.packages[1].values.id = ' shared '
  const result = parseProblemForm(draft)
  assert.equal(result.problem, null)
  for (const collection of ['trucks', 'packages'] as const) {
    for (const row of draft[collection]) assert.match(result.errors[`${collection}.${row.key}.id`], /unique/)
    draft[collection][0].values.id = ' '
    assert.match(parseProblemForm(draft).errors[`${collection}.${draft[collection][0].key}.id`], /required/)
  }
})

test('dimensions reject blanks, nonpositive values, fractions, nonfinite and unsafe integers', () => {
  for (const collection of ['trucks', 'packages'] as const) {
    for (const field of ['width', 'length', 'height'] as const) {
      for (const value of ['', ' ', '0', '-1', '1.5', 'NaN', 'Infinity', '1e400', '9007199254740992']) {
        const draft = createProblemForm(singleTruck)
        const row = draft[collection][0]
        row.values[field] = value
        const result = parseProblemForm(draft)
        assert.equal(result.problem, null, `${collection}.${field}=${value}`)
        assert.ok(result.errors[`${collection}.${row.key}.${field}`])
      }
    }
  }
})

test('capacity, value, weight and ETA reject missing, negative and nonfinite numbers', () => {
  for (const value of ['', ' ', '-1', 'NaN', 'Infinity', '1e400']) {
    const draft = createProblemForm(singleTruck)
    draft.trucks[0].values.max_capacity = value
    for (const field of ['value', 'weight', 'eta'] as const) draft.packages[0].values[field] = value
    const result = parseProblemForm(draft)
    assert.equal(result.problem, null)
    assert.equal(Object.keys(result.errors).length, 4)
  }
  for (const eta of ['0.5', '9007199254740992']) {
    const draft = createProblemForm(singleTruck)
    draft.packages[0].values.eta = eta
    assert.equal(parseProblemForm(draft).problem, null)
  }
})

test('zero metrics and packages too large or heavy to load remain valid input', () => {
  const draft = createProblemForm(singleTruck)
  Object.assign(draft.trucks[0].values, { max_capacity: '0' } satisfies Partial<TruckDraft>)
  Object.assign(draft.packages[0].values, { width: '100', length: '100', height: '100', weight: '500', value: '0', eta: '0' } satisfies Partial<PackageDraft>)
  assert.ok(parseProblemForm(draft).problem)
  draft.packages[0].values.weight = '0'
  assert.ok(parseProblemForm(draft).problem)
})

test('corrections clear validation errors and restore a usable payload', () => {
  let draft = createProblemForm(singleTruck)
  const key = draft.packages[0].key
  draft = problemFormReducer(draft, { type: 'update-package', key, changes: { weight: '' } })
  assert.equal(parseProblemForm(draft).problem, null)
  draft = problemFormReducer(draft, { type: 'update-package', key, changes: { weight: '0.5' } })
  assert.deepEqual(parseProblemForm(draft), { problem: singleTruck, errors: {} })
})

test('form renders all editable fields, accessible labels and row controls', () => {
  const markup = renderToStaticMarkup(<ProblemConfiguration initialProblem={singleTruck} onSubmit={() => {}} />)
  assert.equal((markup.match(/<input /g) ?? []).length, 13)
  assert.match(markup, /Add truck/)
  assert.match(markup, /Add package/)
  assert.match(markup, /aria-label="Remove truck 1" disabled=""/)
  assert.match(markup, /aria-label="Remove package 1"/)
  assert.match(markup, /type="checkbox" checked=""/)
  assert.match(markup, /Apply configuration/)
  const labels = [...markup.matchAll(/<label[^>]*for="([^"]+)"/g)].map((match) => match[1])
  const inputs = [...markup.matchAll(/<input[^>]*id="([^"]+)"/g)].map((match) => match[1])
  assert.deepEqual(labels.sort(), inputs.sort())
  assert.equal(new Set(inputs).size, inputs.length)
})

test('empty package list and multi-truck controls render correctly', () => {
  const empty = renderToStaticMarkup(<ProblemConfiguration initialProblem={{ ...singleTruck, packages: [] }} onSubmit={() => {}} />)
  assert.match(empty, /No packages added/)
  const multi = renderToStaticMarkup(<ProblemConfiguration initialProblem={mockProblem} onSubmit={() => {}} />)
  assert.doesNotMatch(multi, /disabled=""/)
})
