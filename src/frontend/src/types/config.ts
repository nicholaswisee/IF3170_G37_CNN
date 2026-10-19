// Mirrors src/backend/app/schemas/config.py.
import type { Problem } from './experiment'

/** Body of POST /api/configs and the format of an exported configuration file. */
export interface ConfigUpload {
  schema_version: 1
  name: string
  description: string
  problem: Problem
}

export interface SavedConfig {
  id: string
  name: string
  description: string
  /** Built-in configurations ship with the backend and cannot be deleted. */
  builtin: boolean
  /** ISO timestamp; null for built-in configurations. */
  created_at: string | null
  problem: Problem
}

export interface ConfigSummary {
  id: string
  name: string
  description: string
  builtin: boolean
  created_at: string | null
  truck_count: number
  package_count: number
}
