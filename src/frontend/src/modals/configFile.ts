import { checkProblemLimits } from '../api/limits'
import { isProblem } from '../api/validation'
import type { ConfigUpload } from '../types/config'
import type { Limits, Problem } from '../types/experiment'

// Kept in sync with MAX_CONFIG_NAME_LENGTH and MAX_CONFIG_DESCRIPTION_LENGTH in the backend limits.
const MAX_NAME_LENGTH = 80
const MAX_DESCRIPTION_LENGTH = 500

export type ParsedConfigFile = { upload: ConfigUpload; error: null } | { upload: null; error: string }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Readable name from a file name, such as "small-fleet.json" to "small fleet". */
export function nameFromFileName(fileName: string): string {
  const name = fileName.replace(/\.json$/i, '').replace(/[-_]+/g, ' ').trim()
  return (name || 'Imported configuration').slice(0, MAX_NAME_LENGTH)
}

/**
 * Reads an uploaded file. It accepts the export format with schema_version,
 * name, description, and problem, or a bare problem with trucks and packages.
 * Field rules such as positive sizes and unique IDs stay with the backend, which
 * names the exact field that fails.
 */
export function parseConfigFile(text: string, fileName: string, limits: Limits | null): ParsedConfigFile {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    return { upload: null, error: `${fileName} is not valid JSON` }
  }
  if (!isRecord(data)) return { upload: null, error: 'The file must hold a JSON object with trucks and packages' }

  const envelope = 'problem' in data
  const problem = envelope ? data.problem : data
  if (envelope && data.schema_version !== undefined && data.schema_version !== 1) {
    return { upload: null, error: `This file uses configuration format ${String(data.schema_version)}. Only format 1 is supported` }
  }
  if (!isRecord(problem) || !Array.isArray(problem.trucks) || !Array.isArray(problem.packages)) {
    return { upload: null, error: 'The file needs a trucks list and a packages list' }
  }
  if (limits && isProblem(problem)) {
    const limitError = checkProblemLimits(problem, limits)
    if (limitError) return { upload: null, error: limitError }
  }

  const name = envelope && typeof data.name === 'string' && data.name.trim() ? data.name.trim().slice(0, MAX_NAME_LENGTH) : nameFromFileName(fileName)
  const description = envelope && typeof data.description === 'string' ? data.description.trim().slice(0, MAX_DESCRIPTION_LENGTH) : ''
  // Only the problem fields are sent, so files exported from the API with an id or timestamps still import.
  return {
    upload: { schema_version: 1, name, description, problem: { trucks: problem.trucks, packages: problem.packages } as Problem },
    error: null,
  }
}

/** File contents for Export, in the same format the importer reads. */
export function configFileText(name: string, problem: Problem, description = ''): string {
  const file: ConfigUpload = { schema_version: 1, name, description, problem }
  return `${JSON.stringify(file, null, 2)}\n`
}

export function configFileName(name: string): string {
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
  return `${slug || 'configuration'}.json`
}
