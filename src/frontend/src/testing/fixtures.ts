import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { isExperimentResult, isLimits } from '../api/validation'
import type { ExperimentResult, Limits } from '../types/experiment'

/** Reads a backend contract fixture so frontend tests use the exact JSON the backend produces. */
function readBackendFixture(name: string): unknown {
  return JSON.parse(readFileSync(resolve(process.cwd(), '../backend/tests/fixtures', name), 'utf8'))
}

export function readLimitsFixture(): Limits {
  const value = readBackendFixture('limits.json')
  if (!isLimits(value)) throw new Error('backend limits fixture does not satisfy the frontend contract')
  return value
}

export function readExperimentFixture(): ExperimentResult {
  const value = readBackendFixture('experiment_result.json')
  if (!isExperimentResult(value)) throw new Error('backend experiment fixture does not satisfy the frontend contract')
  return value
}
