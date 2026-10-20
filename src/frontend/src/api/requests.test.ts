import assert from 'node:assert/strict'
import test from 'node:test'
import { createProblemForm, parseProblemForm } from '../modals/problemForm'
import { readLimitsFixture } from '../testing/fixtures'
import type { Problem } from '../types/experiment'
import { buildRunRequest, defaultDrafts, parseParameters, parseSeed, visibleFields } from './requests'

const limits = readLimitsFixture()
const problem: Problem = { packages: [], trucks: [{ id: 'T1', width: 1, length: 1, height: 1, max_capacity: 1 }] }

test('configured packages and trucks reach every algorithm with the selected objective', () => {
  const configured: Problem = {
    trucks: [
      { id: 'custom-a', width: 3, length: 4, height: 2, max_capacity: 10 },
      { id: 'custom-b', width: 2, length: 2, height: 1, max_capacity: 5 },
    ],
    packages: [{ id: 'custom-package', width: 1, length: 2, height: 1, value: 12.5, weight: 2, eta: 3, is_fragile: true }],
  }
  const parsed = parseProblemForm(createProblemForm(configured))
  assert.ok(parsed.problem)
  for (const algorithm of ['hill_climbing', 'simulated_annealing', 'genetic_algorithm'] as const) {
    const { parameters } = parseParameters(algorithm, 'sideways', defaultDrafts(limits, algorithm), limits)
    for (const objectiveMode of ['total_value', 'eta_weighted_value'] as const) {
      const request = buildRunRequest({ algorithm, problem: parsed.problem, seed: 123, objectiveMode, parameters })
      assert.deepEqual(request.problem, configured)
      assert.equal(request.objective_mode, objectiveMode)
      assert.equal(request.seed, 123)
      assert.equal(request.algorithm, algorithm)
    }
  }
})

test('backend defaults are valid and complete, including no-elitism GA defaults', () => {
  for (const algorithm of ['hill_climbing', 'simulated_annealing', 'genetic_algorithm'] as const) {
    const parsed = parseParameters(algorithm, 'random_restart', defaultDrafts(limits, algorithm), limits)
    assert.equal(parsed.error, null, algorithm)
    assert.deepEqual(Object.keys(parsed.parameters).sort(), Object.keys(limits.parameters[algorithm]).sort())
  }
  const ga = parseParameters('genetic_algorithm', 'sideways', defaultDrafts(limits, 'genetic_algorithm'), limits)
  assert.equal(ga.parameters.elite_count, 0)
  assert.equal(ga.parameters.crossover_probability, 1)
  assert.equal(ga.parameters.population_size, 50)
  const sa = parseParameters('simulated_annealing', 'sideways', defaultDrafts(limits, 'simulated_annealing'), limits)
  assert.equal(sa.parameters.initial_temperature, null, 'an empty nullable field means automatic temperature')
})

test('only the fields a Hill Climbing variant reads are shown, and fixed fields never are', () => {
  const keys = (variant: Parameters<typeof visibleFields>[1]) => visibleFields('hill_climbing', variant, limits).map((field) => field.key)
  assert.deepEqual(keys('steepest_ascent'), ['max_iterations', 'candidates_per_iteration'])
  assert.deepEqual(keys('sideways'), ['max_iterations', 'candidates_per_iteration', 'max_sideways'])
  assert.deepEqual(keys('random_restart'), ['max_iterations', 'candidates_per_iteration', 'max_restarts'])
  assert.deepEqual(keys('stochastic'), ['max_iterations'])
  assert.ok(!visibleFields('genetic_algorithm', 'sideways', limits).some((field) => field.key === 'elite_count'))
})

test('stochastic HC hides candidate count but sends its backend default', () => {
  const parsed = parseParameters('hill_climbing', 'stochastic', { ...defaultDrafts(limits, 'hill_climbing'), candidates_per_iteration: 'invalid' }, limits)
  assert.equal(parsed.error, null)
  assert.equal(parsed.parameters.candidates_per_iteration, limits.parameters.hill_climbing.candidates_per_iteration.default)
})

test('rejects values outside the backend ranges with the field label and allowed range', () => {
  const highestIterations = limits.parameters.hill_climbing.max_iterations.maximum
  assert.ok(highestIterations !== null)
  const hc = parseParameters('hill_climbing', 'sideways', { ...defaultDrafts(limits, 'hill_climbing'), max_iterations: String(highestIterations + 1) }, limits)
  assert.deepEqual(hc.invalid, ['max_iterations'])
  assert.equal(hc.error, `Max iterations must be 1 to ${highestIterations}`)

  const sa = defaultDrafts(limits, 'simulated_annealing')
  for (const [key, value] of [['alpha', '1'], ['alpha', '0'], ['min_temperature', '0'], ['initial_temperature', '-2'], ['stuck_patience', '2.5']]) {
    const parsed = parseParameters('simulated_annealing', 'sideways', { ...sa, [key]: value }, limits)
    assert.deepEqual(parsed.invalid, [key], `${key}=${value}`)
  }
  const ga = parseParameters('genetic_algorithm', 'sideways', { ...defaultDrafts(limits, 'genetic_algorithm'), population_size: '1', mutation_probability: '1.5' }, limits)
  assert.deepEqual(ga.invalid, ['population_size', 'mutation_probability'])
  assert.match(ga.error ?? '', /^Population size must be 2 to \d+$/)
})

test('hidden variant fields are sent with the backend default even if their draft is invalid', () => {
  const drafts = { ...defaultDrafts(limits, 'hill_climbing'), max_restarts: '999' }
  const parsed = parseParameters('hill_climbing', 'sideways', drafts, limits)
  assert.equal(parsed.error, null)
  assert.equal(parsed.parameters.max_restarts, limits.parameters.hill_climbing.max_restarts.default)
})

test('accepts signed safe integer seeds and rejects fractional or unsafe values', () => {
  for (const seed of [Number.MIN_SAFE_INTEGER, -42, 42, 2147483648, Number.MAX_SAFE_INTEGER]) {
    assert.equal(parseSeed(String(seed), limits).error, null, String(seed))
  }
  for (const text of ['', 'abc', '1.5', String(Number.MAX_SAFE_INTEGER + 2)]) {
    assert.notEqual(parseSeed(text, limits).error, null, text)
  }
})

test('builds the request shape of the API contract', () => {
  const request = buildRunRequest({
    algorithm: 'simulated_annealing', problem, seed: 42, objectiveMode: 'eta_weighted_value', persist: false,
    parameters: { initial_temperature: null, alpha: 0.9, min_temperature: 0.01, max_iterations: 20, stuck_patience: 2 },
  })
  assert.deepEqual(request, {
    algorithm: 'simulated_annealing', problem, seed: 42, objective_mode: 'eta_weighted_value', include_state_history: true, persist: false,
    parameters: { initial_temperature: null, alpha: 0.9, min_temperature: 0.01, max_iterations: 20, stuck_patience: 2 },
  })
  const hc = buildRunRequest({ algorithm: 'hill_climbing', problem, seed: 1, variant: 'stochastic', parameters: {} })
  assert.ok(hc.algorithm === 'hill_climbing')
  assert.equal(hc.variant, 'stochastic')
})
