import type { ConfigSummary, SavedConfig } from '../types/config'
import type {
  ExperimentResult,
  Limits,
  Move,
  NumericRange,
  OptimizationState,
  PackagePlacement,
  PackageSpec,
  Position,
  Problem,
  SearchEvent,
  TruckSpec,
} from '../types/experiment'

const algorithms = new Set(['hill_climbing', 'simulated_annealing', 'genetic_algorithm'])
const objectiveModes = new Set(['total_value', 'eta_weighted_value'])
const hillClimbingVariants = new Set(['steepest_ascent', 'stochastic', 'sideways', 'random_restart'])
const moveTypes = new Set(['SWAP', 'RELOCATE', 'ROTATE'])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || isFiniteNumber(value)
}

function isPackageSpec(value: unknown): value is PackageSpec {
  return isRecord(value)
    && typeof value.id === 'string'
    && Number.isInteger(value.width)
    && Number.isInteger(value.length)
    && Number.isInteger(value.height)
    && isFiniteNumber(value.value)
    && isFiniteNumber(value.weight)
    && typeof value.is_fragile === 'boolean'
    && Number.isInteger(value.eta)
}

function isTruckSpec(value: unknown): value is TruckSpec {
  return isRecord(value)
    && typeof value.id === 'string'
    && Number.isInteger(value.width)
    && Number.isInteger(value.length)
    && Number.isInteger(value.height)
    && isFiniteNumber(value.max_capacity)
}

export function isProblem(value: unknown): value is Problem {
  return isRecord(value)
    && Array.isArray(value.packages)
    && value.packages.every(isPackageSpec)
    && Array.isArray(value.trucks)
    && value.trucks.length > 0
    && value.trucks.every(isTruckSpec)
}

function isPosition(value: unknown): value is Position {
  return isRecord(value) && Number.isInteger(value.x) && Number.isInteger(value.y) && Number.isInteger(value.z)
}

function isPackagePlacement(value: unknown): value is PackagePlacement {
  return isRecord(value)
    && typeof value.package_id === 'string'
    && ((value.truck_id === null && value.position === null)
      || (typeof value.truck_id === 'string' && isPosition(value.position)))
    && typeof value.orientation === 'number'
    && Number.isInteger(value.orientation)
    && value.orientation >= 0 && value.orientation <= 5
}

function isOptimizationState(value: unknown): value is OptimizationState {
  return isRecord(value)
    && Array.isArray(value.placements)
    && value.placements.every(isPackagePlacement)
}

function isMove(value: unknown): value is Move {
  return isRecord(value)
    && typeof value.type === 'string'
    && moveTypes.has(value.type)
    && Array.isArray(value.package_ids)
    && value.package_ids.every((packageId) => typeof packageId === 'string')
    && Array.isArray(value.before)
    && value.before.every(isPackagePlacement)
    && Array.isArray(value.after)
    && value.after.every(isPackagePlacement)
    && isRecord(value.metadata)
}

function isSearchEvent(value: unknown): value is SearchEvent {
  return isRecord(value)
    && isFiniteNumber(value.iteration)
    && isFiniteNumber(value.current_score)
    && isFiniteNumber(value.best_score)
    && isNullableNumber(value.candidate_score)
    && isNullableNumber(value.mean_score)
    && (value.accepted === null || typeof value.accepted === 'boolean')
    && (value.move === null || isMove(value.move))
    && isNullableNumber(value.temperature)
    && isNullableNumber(value.acceptance_probability)
    && (value.state_snapshot === null || isOptimizationState(value.state_snapshot))
    && isRecord(value.metadata)
}

function isNumericRange(value: unknown): value is NumericRange {
  return isRecord(value)
    && typeof value.integer === 'boolean'
    && typeof value.nullable === 'boolean'
    && isNullableNumber(value.minimum)
    && isNullableNumber(value.exclusive_minimum)
    && isNullableNumber(value.maximum)
    && isNullableNumber(value.exclusive_maximum)
    && isNullableNumber(value.default)
}

function isPositiveInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) > 0
}

export function isLimits(value: unknown): value is Limits {
  if (!isRecord(value) || !isRecord(value.problem) || !isRecord(value.parameters)) return false
  const { problem, parameters } = value
  return isPositiveInteger(problem.max_packages)
    && isPositiveInteger(problem.max_trucks)
    && isPositiveInteger(problem.max_id_length)
    && isPositiveInteger(problem.max_total_truck_volume)
    && isNumericRange(value.seed)
    && isPositiveInteger(value.max_request_bytes)
    && [...algorithms].every((algorithm) => isRecord(parameters[algorithm])
      && Object.values(parameters[algorithm]).every(isNumericRange))
}

function hasConfigFields(value: Record<string, unknown>): boolean {
  return typeof value.id === 'string'
    && typeof value.name === 'string'
    && typeof value.description === 'string'
    && typeof value.builtin === 'boolean'
    && (value.created_at === null || typeof value.created_at === 'string')
}

export function isSavedConfig(value: unknown): value is SavedConfig {
  return isRecord(value) && hasConfigFields(value) && isProblem(value.problem)
}

export function isConfigSummary(value: unknown): value is ConfigSummary {
  return isRecord(value)
    && hasConfigFields(value)
    && Number.isSafeInteger(value.truck_count)
    && Number.isSafeInteger(value.package_count)
}

export function isExperimentResult(value: unknown): value is ExperimentResult {
  return isRecord(value)
    && typeof value.id === 'string'
    && isProblem(value.problem)
    && typeof value.algorithm === 'string'
    && algorithms.has(value.algorithm)
    && (value.variant === null || (typeof value.variant === 'string' && hillClimbingVariants.has(value.variant)))
    && typeof value.objective_mode === 'string'
    && objectiveModes.has(value.objective_mode)
    && Number.isSafeInteger(value.seed)
    && isRecord(value.parameters)
    && isOptimizationState(value.initial_state)
    && isOptimizationState(value.final_state)
    && isOptimizationState(value.best_state)
    && isFiniteNumber(value.initial_score)
    && isFiniteNumber(value.final_score)
    && isFiniteNumber(value.best_score)
    && isFiniteNumber(value.runtime_ms)
    && isFiniteNumber(value.iterations)
    && Array.isArray(value.history)
    && value.history.every(isSearchEvent)
    && isRecord(value.metadata)
}
