import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { renderToStaticMarkup } from 'react-dom/server'
import { HillClimbingParameters, type HillClimbingFormValues } from './HillClimbingParameters'
import { ResultSummary } from './ResultComparison'
import { buildRunRequest, defaultHillClimbingParameters, selectHillClimbingParameters, validateHillClimbingInput } from '../api/requests'
import { isExperimentResult } from '../api/validation'
import type { ExperimentResult, HillClimbingVariant, Problem } from '../types/experiment'

const problem: Problem = { packages: [], trucks: [{ id: 'T1', width: 1, length: 1, height: 1, max_capacity: 1 }] }
const fixture: unknown = JSON.parse(readFileSync(resolve(process.cwd(), '../backend/tests/fixtures/experiment_result.json'), 'utf8'))
assert.ok(isExperimentResult(fixture))

function form(variant: HillClimbingVariant): HillClimbingFormValues {
  return { variant, max_iterations: '2000', candidates_per_iteration: '50', max_sideways: '100', max_restarts: '10' }
}

function inputIds(variant: HillClimbingVariant): string[] {
  const markup = renderToStaticMarkup(<HillClimbingParameters values={form(variant)} onChange={() => {}} />)
  return (markup.match(/<input[^>]+id="([^"]+)"/g) ?? []).map((input) => /id="([^"]+)"/.exec(input)?.[1] ?? '')
}

test('HC controls list every variant and show only the fields the variant reads', () => {
  const markup = renderToStaticMarkup(<HillClimbingParameters values={form('sideways')} onChange={() => {}} />)
  for (const value of ['steepest_ascent', 'stochastic', 'sideways', 'random_restart']) assert.ok(markup.includes(`value="${value}"`))
  const common = ['hc-max-iterations', 'hc-candidates']
  assert.deepEqual(inputIds('steepest_ascent'), common)
  assert.deepEqual(inputIds('stochastic'), common)
  assert.deepEqual(inputIds('sideways'), [...common, 'hc-max-sideways'])
  assert.deepEqual(inputIds('random_restart'), [...common, 'hc-max-restarts'])
  assert.match(renderToStaticMarkup(<HillClimbingParameters values={form('random_restart')} onChange={() => {}} />), /max="20"/)
})

test('HC request sends only the parameters relevant to the chosen variant', () => {
  const expected: Record<HillClimbingVariant, string[]> = {
    steepest_ascent: ['max_iterations', 'candidates_per_iteration'],
    stochastic: ['max_iterations', 'candidates_per_iteration'],
    sideways: ['max_iterations', 'candidates_per_iteration', 'max_sideways'],
    random_restart: ['max_iterations', 'candidates_per_iteration', 'max_restarts'],
  }
  for (const variant of Object.keys(expected) as HillClimbingVariant[]) {
    const request = buildRunRequest({
      algorithm: 'hill_climbing', problem, seed: 7, variant,
      hillClimbingParameters: selectHillClimbingParameters(variant, { ...defaultHillClimbingParameters, max_restarts: 3 }),
    })
    assert.equal(request.algorithm === 'hill_climbing' && request.variant, variant)
    assert.deepEqual(Object.keys(request.parameters ?? {}), expected[variant])
  }
  assert.deepEqual(buildRunRequest({ algorithm: 'hill_climbing', problem, seed: 7 }).parameters, defaultHillClimbingParameters)
})

test('HC validation enforces backend budgets only for relevant fields', () => {
  const base = { ...defaultHillClimbingParameters, variant: 'sideways' as HillClimbingVariant, seed: 42 }
  assert.equal(validateHillClimbingInput(base), null)
  assert.ok(validateHillClimbingInput({ ...base, max_iterations: 2001 }))
  assert.ok(validateHillClimbingInput({ ...base, max_iterations: 0 }))
  assert.ok(validateHillClimbingInput({ ...base, candidates_per_iteration: 51 }))
  assert.ok(validateHillClimbingInput({ ...base, max_sideways: -1 }))
  assert.ok(validateHillClimbingInput({ ...base, max_sideways: 1.5 }))
  assert.ok(validateHillClimbingInput({ ...base, seed: 1.5 }))
  assert.equal(validateHillClimbingInput({ ...base, max_restarts: 99 }), null)
  const restart = { ...base, variant: 'random_restart' as HillClimbingVariant }
  assert.equal(validateHillClimbingInput({ ...restart, max_restarts: 0 }), null)
  assert.equal(validateHillClimbingInput({ ...restart, max_restarts: 20 }), null)
  assert.ok(validateHillClimbingInput({ ...restart, max_restarts: 21 }))
  assert.equal(validateHillClimbingInput({ ...restart, max_sideways: -5 }), null)
})

test('HC summary renders variant-specific metadata only for that variant', () => {
  const run = (variant: HillClimbingVariant, metadata: ExperimentResult['metadata']): ExperimentResult =>
    ({ ...fixture, algorithm: 'hill_climbing', variant, iterations: 12, metadata })
  const sideways = renderToStaticMarkup(<ResultSummary experiment={run('sideways', { sideways_moves: 4, termination_reason: 'max_sideways' })} />)
  assert.match(sideways, /Iterations<\/dt><dd>12/)
  assert.match(sideways, /Sideways moves<\/dt><dd>4/)
  assert.match(sideways, /max sideways/)
  assert.doesNotMatch(sideways, /Restarts/)
  const restart = renderToStaticMarkup(<ResultSummary experiment={run('random_restart', {
    restarts_performed: 2, iterations_per_restart: [3, 5, 4], best_score_per_restart: [10, 12.5, 11],
    termination_reason: 'max_restarts',
  })} />)
  assert.match(restart, /Restarts<\/dt><dd>2/)
  assert.match(restart, /Iterations per restart<\/dt><dd>3, 5, 4/)
  assert.match(restart, /Best per restart<\/dt><dd>10, 12.5, 11/)
  assert.doesNotMatch(restart, /Sideways moves/)
  const steepest = renderToStaticMarkup(<ResultSummary experiment={run('steepest_ascent', { termination_reason: 'local_optimum' })} />)
  assert.match(steepest, /local optimum/)
  assert.doesNotMatch(steepest, /Sideways moves|Restarts/)
})
