import assert from 'node:assert/strict'
import test from 'node:test'
import { buildRunRequest, defaultGeneticAlgorithmParameters, defaultSimulatedAnnealingParameters, validateGeneticAlgorithmInput, validateSimulatedAnnealingInput, validateSeed } from './requests'
import type { Problem } from '../types/experiment'
import { createProblemForm, parseProblemForm } from '../components/problemForm'

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
    assert.equal(buildRunRequest({ algorithm, problem: parsed.problem, seed: 42 }).objective_mode, 'total_value')
    for (const objectiveMode of ['total_value', 'eta_weighted_value'] as const) {
      const request = buildRunRequest({ algorithm, problem: parsed.problem, seed: 123, objectiveMode })
      assert.deepEqual(request.problem, configured)
      assert.equal(request.objective_mode, objectiveMode)
      assert.equal(request.seed, 123)
    }
  }
})

test('keeps official GA defaults unless callers provide overrides', () => {
  const request = buildRunRequest({ algorithm: 'genetic_algorithm', problem, seed: 42 })
  assert.deepEqual(request.parameters, defaultGeneticAlgorithmParameters)
  assert.deepEqual(defaultGeneticAlgorithmParameters, {
    population_size: 50, generations: 100, crossover_probability: 0.8,
    mutation_probability: 0.2, elite_count: 1,
  })
})

test('builds the Section 6D GA smoke request with supplied parameter overrides', () => {
  const request = buildRunRequest({
    algorithm: 'genetic_algorithm', problem, seed: 42, persist: false,
    geneticAlgorithmParameters: {
      population_size: 6, generations: 5, crossover_probability: 0.8,
      mutation_probability: 0.2, elite_count: 99,
    },
  })
  assert.deepEqual(request, {
    algorithm: 'genetic_algorithm', problem, seed: 42, objective_mode: 'total_value',
    include_state_history: true, persist: false,
    parameters: { population_size: 6, generations: 5, crossover_probability: 0.8, mutation_probability: 0.2, elite_count: 1 },
  })
})

test('rejects invalid GA form values including non-integers and non-finite probabilities', () => {
  assert.equal(validateGeneticAlgorithmInput({ population_size: 2, generations: 1, crossover_probability: 0, mutation_probability: 1, seed: -9007199254740991 }), null)
  assert.equal(validateGeneticAlgorithmInput({ population_size: 100, generations: 200, crossover_probability: 0, mutation_probability: 1, seed: 2147483648 }), null)
  for (const input of [
    { population_size: 1, generations: 1, crossover_probability: 0, mutation_probability: 0, seed: 42 },
    { population_size: 6, generations: 0, crossover_probability: 0, mutation_probability: 0, seed: 42 },
    { population_size: 6, generations: 5, crossover_probability: NaN, mutation_probability: 0, seed: 42 },
    { population_size: 6, generations: 5, crossover_probability: 0, mutation_probability: Infinity, seed: 42 },
    { population_size: 6, generations: 5, crossover_probability: -0.01, mutation_probability: 0, seed: 42 },
    { population_size: 6, generations: 5, crossover_probability: 1.01, mutation_probability: 0, seed: 42 },
    { population_size: 6, generations: 5, crossover_probability: 0, mutation_probability: -0.01, seed: 42 },
    { population_size: 6, generations: 5, crossover_probability: 0, mutation_probability: 1.01, seed: 42 },
    { population_size: 101, generations: 5, crossover_probability: 0, mutation_probability: 0, seed: 42 },
    { population_size: 6, generations: 201, crossover_probability: 0, mutation_probability: 0, seed: 42 },
    { population_size: 6.5, generations: 5, crossover_probability: 0, mutation_probability: 0, seed: 42 },
    { population_size: 6, generations: 5.5, crossover_probability: 0, mutation_probability: 0, seed: 42 },
  ]) assert.notEqual(validateGeneticAlgorithmInput(input), null)
})

test('accepts signed safe integer seeds and rejects fractional or unsafe values', () => {
  for (const seed of [Number.MIN_SAFE_INTEGER, -42, 42, 2147483648, Number.MAX_SAFE_INTEGER]) {
    assert.equal(validateSeed(seed), null)
  }
  for (const seed of [NaN, Infinity, 1.5, Number.MIN_SAFE_INTEGER - 1, Number.MAX_SAFE_INTEGER + 1]) {
    assert.notEqual(validateSeed(seed), null)
  }
})

test('builds SA requests with custom parameters and preserves other algorithms', () => {
  const parameters = { initial_temperature: 10, alpha: 0.9, min_temperature: 0.01, max_iterations: 20, stuck_patience: 2 }
  const request = buildRunRequest({ algorithm: 'simulated_annealing', problem, seed: 123,
    objectiveMode: 'eta_weighted_value', persist: false, simulatedAnnealingParameters: parameters })
  assert.deepEqual(request, { algorithm: 'simulated_annealing', problem, seed: 123,
    objective_mode: 'eta_weighted_value', persist: false, include_state_history: true, parameters })
  const defaults = buildRunRequest({ algorithm: 'simulated_annealing', problem, seed: 42 })
  assert.ok(defaults.algorithm === 'simulated_annealing')
  assert.deepEqual(defaults.parameters, defaultSimulatedAnnealingParameters)
  assert.equal(defaults.parameters.initial_temperature, null)
  assert.notEqual(defaults.parameters, defaultSimulatedAnnealingParameters)
  const ga = buildRunRequest({ algorithm: 'genetic_algorithm', problem, seed: 42, simulatedAnnealingParameters: parameters })
  assert.deepEqual(ga.parameters, defaultGeneticAlgorithmParameters)
})

test('validates SA boundaries including automatic temperature and API iteration cap', () => {
  const valid = { ...defaultSimulatedAnnealingParameters, seed: 42 }
  assert.equal(validateSimulatedAnnealingInput(valid), null)
  assert.equal(validateSimulatedAnnealingInput({ ...valid, initial_temperature: 1, max_iterations: 1, stuck_patience: 1 }), null)
  for (const invalid of [
    { initial_temperature: 0 }, { initial_temperature: -1 }, { initial_temperature: Infinity }, { initial_temperature: NaN },
    { alpha: 0 }, { alpha: 1 }, { alpha: NaN }, { alpha: Infinity },
    { min_temperature: 0 }, { min_temperature: -1 }, { min_temperature: Infinity },
    { max_iterations: 0 }, { max_iterations: 5001 }, { max_iterations: 1.5 },
    { stuck_patience: 0 }, { stuck_patience: 2.5 }, { stuck_patience: Infinity },
    { seed: NaN }, { seed: Number.MAX_SAFE_INTEGER + 1 },
  ]) assert.notEqual(validateSimulatedAnnealingInput({ ...valid, ...invalid }), null, JSON.stringify(invalid))
})
