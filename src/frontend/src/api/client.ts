import type {
  ExperimentListResponse,
  ExperimentResult,
  RunExperimentRequest,
} from '../types/experiment'
import { isExperimentResult } from './validation'

const apiBaseUrl = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init)

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`)
  }

  return response.json() as Promise<T>
}

export function listExperiments(): Promise<ExperimentListResponse> {
  return request<ExperimentListResponse>('/api/experiments')
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
