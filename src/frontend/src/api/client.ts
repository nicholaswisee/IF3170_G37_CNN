import type {
  ExperimentListResponse,
  ExperimentResult,
  Problem,
  RunExperimentRequest,
} from '../types/experiment'
import { isExperimentResult } from './validation'
import { formatApiError } from './errors'

const apiBaseUrl = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init)

  if (!response.ok) {
    let detail: unknown
    try {
      const body: unknown = await response.json()
      if (typeof body === 'object' && body !== null && 'detail' in body) detail = body.detail
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error
    }
    throw new Error(formatApiError(response.status, detail))
  }

  return response.json() as Promise<T>
}

export async function validateProblem(problem: Problem): Promise<void> {
  const response = await request<unknown>('/api/problems/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(problem),
  })
  if (typeof response !== 'object' || response === null || !('valid' in response) || response.valid !== true) {
    throw new Error('Invalid problem validation response.')
  }
}

export async function listExperiments(): Promise<ExperimentListResponse> {
  const response: unknown = await request<unknown>('/api/experiments')
  if (typeof response !== 'object' || response === null || Array.isArray(response)
    || !('experiments' in response) || !Array.isArray(response.experiments)
    || !response.experiments.every(isExperimentResult)) {
    throw new Error('Invalid experiment list response: expected an experiments array of valid results.')
  }

  return { experiments: response.experiments }
}

export function runExperiment(requestBody: RunExperimentRequest): Promise<ExperimentResult> {
  return request<unknown>('/api/experiments/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody),
  }).then((result) => {
    if (!isExperimentResult(result)) {
      throw new Error('Invalid experiment response')
    }

    return result
  })
}
