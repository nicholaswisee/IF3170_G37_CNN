import type { ExperimentResult, Move, OptimizationState, Position, SearchEvent } from '../types/experiment'

const algorithms = new Set(['hill_climbing', 'simulated_annealing', 'genetic_algorithm'])
const moveTypes = new Set(['SWAP', 'RELOCATE', 'ROTATE'])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isPosition(value: unknown): value is Position {
  return isRecord(value) && typeof value.x === 'number' && typeof value.y === 'number' && typeof value.z === 'number'
}

function isOptimizationState(value: unknown): value is OptimizationState {
  return isRecord(value)
    && Array.isArray(value.placements)
    && typeof value.objective_value === 'number'
    && typeof value.total_weight === 'number'
}

function isMove(value: unknown): value is Move {
  return isRecord(value)
    && typeof value.type === 'string'
    && moveTypes.has(value.type)
    && Array.isArray(value.package_ids)
    && value.package_ids.every((packageId) => typeof packageId === 'string')
    && (value.source === undefined || value.source === null || isPosition(value.source))
    && (value.destination === undefined || value.destination === null || isPosition(value.destination))
    && isRecord(value.metadata)
}

function isSearchEvent(value: unknown): value is SearchEvent {
  return isRecord(value)
    && typeof value.iteration === 'number'
    && typeof value.current_score === 'number'
    && typeof value.candidate_score === 'number'
    && typeof value.accepted === 'boolean'
    && (value.move === null || isMove(value.move))
    && isRecord(value.metadata)
}

export function isExperimentResult(value: unknown): value is ExperimentResult {
  return isRecord(value)
    && typeof value.id === 'string'
    && typeof value.algorithm === 'string'
    && algorithms.has(value.algorithm)
    && typeof value.seed === 'number'
    && isOptimizationState(value.initial_state)
    && isOptimizationState(value.final_state)
    && typeof value.initial_score === 'number'
    && typeof value.final_score === 'number'
    && typeof value.runtime_ms === 'number'
    && typeof value.iterations === 'number'
    && Array.isArray(value.history)
    && value.history.every(isSearchEvent)
    && isRecord(value.metadata)
}
