import type {
  Algorithm,
  GeneticAlgorithmParameters,
  HillClimbingParameters,
  HillClimbingVariant,
  Limits,
  ObjectiveMode,
  Problem,
  RunExperimentRequest,
  SimulatedAnnealingParameters,
} from '../types/experiment'
import { checkNumber, isFixed } from './limits'

/** How a backend parameter appears in the form. Ranges and defaults come from GET /api/limits. */
export interface ParameterField {
  key: string
  label: string
  hint?: string
  /** Stepper increment for decimal fields; whole-number fields always step by 1. */
  step?: number
  /** Hill Climbing variants that read this field; omitted means every variant. */
  variants?: HillClimbingVariant[]
}

export const PARAMETER_FIELDS: Record<Algorithm, ParameterField[]> = {
  hill_climbing: [
    { key: 'max_iterations', label: 'Max iterations' },
    { key: 'candidates_per_iteration', label: 'Candidates per iteration', hint: 'Neighbors sampled each iteration' },
    { key: 'max_sideways', label: 'Max sideways moves', hint: 'Equal score moves allowed in a row', variants: ['sideways'] },
    { key: 'max_restarts', label: 'Max restarts', hint: 'Climbs run this many times plus one', variants: ['random_restart'] },
  ],
  simulated_annealing: [
    { key: 'initial_temperature', label: 'Initial temperature', hint: 'Auto uses the mean package value', step: 1 },
    { key: 'alpha', label: 'Cooling rate alpha', step: 0.005 },
    { key: 'min_temperature', label: 'Minimum temperature', step: 0.001 },
    { key: 'max_iterations', label: 'Max iterations' },
    { key: 'stuck_patience', label: 'Stuck patience', hint: 'Iterations without a new best score' },
  ],
  genetic_algorithm: [
    { key: 'population_size', label: 'Population size' },
    { key: 'generations', label: 'Generations' },
    { key: 'crossover_probability', label: 'Crossover probability', step: 0.05 },
    { key: 'mutation_probability', label: 'Mutation probability', step: 0.05 },
  ],
}

/** Form text for each parameter; an empty string on a nullable field means automatic. */
export type ParameterDrafts = Record<string, string>

export function defaultDrafts(limits: Limits, algorithm: Algorithm): ParameterDrafts {
  return Object.fromEntries(Object.entries(limits.parameters[algorithm])
    .map(([key, range]) => [key, range.default === null ? '' : String(range.default)]))
}

export function visibleFields(algorithm: Algorithm, variant: HillClimbingVariant, limits: Limits): ParameterField[] {
  const ranges = limits.parameters[algorithm]
  return PARAMETER_FIELDS[algorithm].filter((field) => ranges[field.key] !== undefined
    && !isFixed(ranges[field.key])
    && (algorithm !== 'hill_climbing' || !field.variants || field.variants.includes(variant)))
}

export interface ParsedParameters {
  parameters: Record<string, number | null>
  /** First problem found, phrased for a toast; null when every field is valid. */
  error: string | null
  /** Parameter keys that failed validation. */
  invalid: string[]
}

/**
 * Validates the shown fields against the backend ranges. Hidden and fixed
 * parameters are sent with the backend default so the request is complete.
 */
export function parseParameters(
  algorithm: Algorithm,
  variant: HillClimbingVariant,
  drafts: ParameterDrafts,
  limits: Limits,
): ParsedParameters {
  const shown = new Map(visibleFields(algorithm, variant, limits).map((field) => [field.key, field]))
  const parameters: Record<string, number | null> = {}
  const invalid: string[] = []
  let error: string | null = null
  for (const [key, range] of Object.entries(limits.parameters[algorithm])) {
    const field = shown.get(key)
    if (!field) {
      parameters[key] = range.default
      continue
    }
    const text = (drafts[key] ?? '').trim()
    const value = text === '' ? null : Number(text)
    const problem = checkNumber(field.label, value, range)
    if (problem) {
      invalid.push(key)
      error ??= problem
    }
    parameters[key] = value
  }
  return { parameters, error, invalid }
}

export function parseSeed(text: string, limits: Limits): { seed: number; error: string | null } {
  const seed = text.trim() === '' ? Number.NaN : Number(text)
  return { seed, error: checkNumber('Seed', Number.isNaN(seed) ? null : seed, { ...limits.seed, nullable: false }) }
}

interface RunRequestOptions {
  algorithm: Algorithm
  problem: Problem
  seed: number
  parameters: Record<string, number | null>
  objectiveMode?: ObjectiveMode
  variant?: HillClimbingVariant
  includeStateHistory?: boolean
  persist?: boolean
}

/** Build a single-run request with the full problem, as the API contract requires. */
export function buildRunRequest({
  algorithm,
  problem,
  seed,
  parameters,
  objectiveMode = 'total_value',
  variant = 'sideways',
  includeStateHistory = true,
  persist = true,
}: RunRequestOptions): RunExperimentRequest {
  const common = {
    problem,
    objective_mode: objectiveMode,
    seed,
    include_state_history: includeStateHistory,
    persist,
  }
  switch (algorithm) {
    case 'hill_climbing':
      return { ...common, algorithm, variant, parameters: { ...parameters } as Partial<HillClimbingParameters> }
    case 'simulated_annealing':
      return { ...common, algorithm, parameters: { ...parameters } as Partial<SimulatedAnnealingParameters> }
    case 'genetic_algorithm':
      return { ...common, algorithm, parameters: { ...parameters } as Partial<GeneticAlgorithmParameters> }
  }
}
