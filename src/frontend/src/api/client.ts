import type { ConfigSummary, ConfigUpload, SavedConfig } from '../types/config'
import type {
  ExperimentListResponse,
  ExperimentResult,
  Limits,
  Problem,
  RunExperimentRequest,
} from '../types/experiment'
import { isConfigSummary, isExperimentResult, isLimits, isSavedConfig } from './validation'
import { formatApiError } from './errors'

const apiBaseUrl = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

/** Sends the request and throws a readable error for any non-2xx status. */
async function send(path: string, init?: RequestInit): Promise<Response> {
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

  return response
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await send(path, init)
  return response.json() as Promise<T>
}

export async function getLimits(): Promise<Limits> {
  const response = await request<unknown>('/api/limits')
  if (!isLimits(response)) throw new Error('The backend sent limits in an unexpected format.')
  return response
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

export async function listConfigs(): Promise<ConfigSummary[]> {
  const response: unknown = await request<unknown>('/api/configs')
  if (typeof response !== 'object' || response === null || !('configs' in response)
    || !Array.isArray(response.configs) || !response.configs.every(isConfigSummary)) {
    throw new Error('Invalid configuration list response.')
  }
  return response.configs
}

export async function getConfig(id: string): Promise<SavedConfig> {
  const response = await request<unknown>(`/api/configs/${encodeURIComponent(id)}`)
  if (!isSavedConfig(response)) throw new Error('Invalid configuration response.')
  return response
}

export async function uploadConfig(upload: ConfigUpload): Promise<SavedConfig> {
  const response = await request<unknown>('/api/configs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(upload),
  })
  if (!isSavedConfig(response)) throw new Error('Invalid configuration response.')
  return response
}

export async function deleteConfig(id: string): Promise<void> {
  await send(`/api/configs/${encodeURIComponent(id)}`, { method: 'DELETE' })
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
