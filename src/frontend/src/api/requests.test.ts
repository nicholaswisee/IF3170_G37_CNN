import assert from 'node:assert/strict'
import test from 'node:test'
import { buildRunRequest, defaultGeneticAlgorithmParameters, validateGeneticAlgorithmInput, validateSeed } from './requests'
import type { Problem } from '../types/experiment'

const problem: Problem = { packages: [], trucks: [{ id: 'T1', width: 1, length: 1, height: 1, max_capacity: 1 }] }

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
