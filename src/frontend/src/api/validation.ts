import type {
  ExperimentResult,
  Move,
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

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === 'number'
}

function isPackageSpec(value: unknown): value is PackageSpec {
  return isRecord(value)
    && typeof value.id === 'string'
    && Number.isInteger(value.width)
    && Number.isInteger(value.length)
    && Number.isInteger(value.height)
    && typeof value.value === 'number'
    && typeof value.weight === 'number'
    && typeof value.is_fragile === 'boolean'
    && Number.isInteger(value.eta)
}

function isTruckSpec(value: unknown): value is TruckSpec {
  return isRecord(value)
    && typeof value.id === 'string'
    && Number.isInteger(value.width)
    && Number.isInteger(value.length)
    && Number.isInteger(value.height)
    && typeof value.max_capacity === 'number'
}

function isProblem(value: unknown): value is Problem {
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
    && typeof value.iteration === 'number'
    && typeof value.current_score === 'number'
    && typeof value.best_score === 'number'
    && isNullableNumber(value.candidate_score)
    && isNullableNumber(value.mean_score)
    && (value.accepted === null || typeof value.accepted === 'boolean')
    && (value.move === null || isMove(value.move))
    && isNullableNumber(value.temperature)
    && isNullableNumber(value.acceptance_probability)
    && (value.state_snapshot === null || isOptimizationState(value.state_snapshot))
    && isRecord(value.metadata)
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
    && typeof value.seed === 'number'
    && isRecord(value.parameters)
    && isOptimizationState(value.initial_state)
    && isOptimizationState(value.final_state)
    && isOptimizationState(value.best_state)
    && typeof value.initial_score === 'number'
    && typeof value.final_score === 'number'
    && typeof value.best_score === 'number'
    && typeof value.runtime_ms === 'number'
    && typeof value.iterations === 'number'
    && Array.isArray(value.history)
    && value.history.every(isSearchEvent)
    && isRecord(value.metadata)
}
