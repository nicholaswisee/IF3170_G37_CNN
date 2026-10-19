// Mirrors the frozen backend contract in src/backend/app/schemas/experiment.py.

export type Algorithm = 'hill_climbing' | 'simulated_annealing' | 'genetic_algorithm'

export type ObjectiveMode = 'total_value' | 'eta_weighted_value'

export type HillClimbingVariant = 'steepest_ascent' | 'stochastic' | 'sideways' | 'random_restart'

export type Orientation = 0 | 1 | 2 | 3 | 4 | 5

export interface PackageSpec {
  id: string
  width: number
  length: number
  height: number
  value: number
  weight: number
  is_fragile: boolean
  eta: number
}

export interface TruckSpec {
  id: string
  width: number
  length: number
  height: number
  max_capacity: number
}

export interface Problem {
  packages: PackageSpec[]
  trucks: TruckSpec[]
}

export interface Position {
  x: number
  y: number
  z: number
}

export interface PackagePlacement {
  package_id: string
  truck_id: string | null
  position: Position | null
  orientation: Orientation
}

export interface Move {
  type: 'SWAP' | 'RELOCATE' | 'ROTATE'
  package_ids: string[]
  before: PackagePlacement[]
  after: PackagePlacement[]
  metadata: Record<string, unknown>
}

/** Backend `State`: placement decisions only; scores and validity are derived. */
export interface OptimizationState {
  placements: PackagePlacement[]
}

export interface HillClimbingParameters {
  max_iterations: number
  candidates_per_iteration: number
  max_sideways: number
  max_restarts: number
}

export interface SimulatedAnnealingParameters {
  /** null lets the backend derive max(mean(package.value), 1.0). */
  initial_temperature: number | null
  alpha: number
  min_temperature: number
  max_iterations: number
  stuck_patience: number
}

export interface GeneticAlgorithmParameters {
  population_size: number
  generations: number
  crossover_probability: number
  mutation_probability: number
  elite_count: number
}

/** Fields the backend defaults are optional; parameter fields default individually. */
interface RunRequestBase {
  problem: Problem
  objective_mode?: ObjectiveMode
  seed: number
  include_state_history?: boolean
  persist?: boolean
}

export interface HillClimbingRequest extends RunRequestBase {
  algorithm: 'hill_climbing'
  variant?: HillClimbingVariant
  parameters?: Partial<HillClimbingParameters>
}

export interface SimulatedAnnealingRequest extends RunRequestBase {
  algorithm: 'simulated_annealing'
  parameters?: Partial<SimulatedAnnealingParameters>
}

export interface GeneticAlgorithmRequest extends RunRequestBase {
  algorithm: 'genetic_algorithm'
  parameters?: Partial<GeneticAlgorithmParameters>
}

export type RunExperimentRequest = HillClimbingRequest | SimulatedAnnealingRequest | GeneticAlgorithmRequest

/**
 * Algorithm-neutral history entry. For GA, iteration is the generation index,
 * current_score the generation max, and mean_score the population mean. Fields
 * an algorithm does not use are null; state_snapshot is null in batch runs.
 */
export interface SearchEvent {
  iteration: number
  current_score: number
  best_score: number
  candidate_score: number | null
  mean_score: number | null
  accepted: boolean | null
  move: Move | null
  temperature: number | null
  acceptance_probability: number | null
  state_snapshot: OptimizationState | null
  metadata: Record<string, unknown>
}

export interface ExperimentResult {
  id: string
  problem: Problem
  algorithm: Algorithm
  variant: HillClimbingVariant | null
  objective_mode: ObjectiveMode
  seed: number
  parameters: Record<string, unknown>
  initial_state: OptimizationState
  final_state: OptimizationState
  best_state: OptimizationState
  initial_score: number
  final_score: number
  best_score: number
  runtime_ms: number
  iterations: number
  history: SearchEvent[]
  metadata: Record<string, unknown>
}

export interface ExperimentListResponse {
  experiments: ExperimentResult[]
}

/** Bounds of one numeric input from GET /api/limits; null bounds are open. */
export interface NumericRange {
  integer: boolean
  nullable: boolean
  minimum: number | null
  exclusive_minimum: number | null
  maximum: number | null
  exclusive_maximum: number | null
  default: number | null
}

export interface ProblemLimits {
  max_packages: number
  max_trucks: number
  max_id_length: number
  max_total_truck_volume: number
}

/** Backend `LimitsResponse`: the only source of input limits for the UI. */
export interface Limits {
  problem: ProblemLimits
  seed: NumericRange
  max_request_bytes: number
  parameters: Record<Algorithm, Record<string, NumericRange>>
}
