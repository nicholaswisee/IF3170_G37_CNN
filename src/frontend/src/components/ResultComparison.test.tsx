import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { renderToStaticMarkup } from 'react-dom/server'
import test from 'node:test'
import { ExperimentComparisonTable, ResultSummary } from './ResultComparison'
import { isExperimentResult } from '../api/validation'
import type { ExperimentResult } from '../types/experiment'

const fixtureValue: unknown = JSON.parse(readFileSync(resolve(process.cwd(), '../backend/tests/fixtures/experiment_result.json'), 'utf8'))
assert.ok(isExperimentResult(fixtureValue))
const fixture: ExperimentResult = fixtureValue

test('renders HC, SA, and GA in the generic comparison table and summarizes the active run', () => {
  const runs: ExperimentResult[] = [
    { ...fixture, id: 'hc-run', algorithm: 'hill_climbing', variant: 'sideways' },
    { ...fixture, id: 'sa-run', algorithm: 'simulated_annealing', variant: null },
    { ...fixture, id: 'ga-run', algorithm: 'genetic_algorithm', variant: null },
  ]
  const table = renderToStaticMarkup(<ExperimentComparisonTable experiments={runs} selectedId="sa-run" onSelect={() => {}} />)
  const summary = renderToStaticMarkup(<ResultSummary experiment={runs[1]} />)

  for (const algorithm of ['Hill Climbing', 'Simulated Annealing', 'Genetic Algorithm']) {
    assert.match(table, new RegExp(algorithm))
  }
  assert.match(table, /aria-selected="true"/)
  assert.match(summary, /Active run summary/)
  assert.match(summary, /Initial/)
  assert.match(summary, /Final/)
  assert.match(summary, /Best/)
  assert.match(summary, /Runtime/)
  assert.match(summary, /seed 42/)
})
