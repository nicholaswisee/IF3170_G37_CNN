export type Algorithm = 'hill_climbing' | 'simulated_annealing' | 'genetic_algorithm'

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
  source?: Position | null
  destination?: Position | null
  metadata: Record<string, unknown>
}

export interface SearchEvent {
  iteration: number
  current_score: number
  candidate_score: number
  accepted: boolean
  move: Move | null
  metadata: Record<string, unknown>
}

export interface OptimizationState {
  placements: PackagePlacement[]
}

export interface ExperimentResult {
  id: string
  algorithm: Algorithm
  seed: number
  initial_state: OptimizationState
  final_state: OptimizationState
  initial_score: number
  final_score: number
  runtime_ms: number
  iterations: number
  history: SearchEvent[]
  metadata: Record<string, unknown>
}

export interface RunExperimentRequest {
  algorithm: Algorithm
  seed: number
  parameters: Record<string, unknown>
}

export interface HealthResponse {
  status: 'ok'
  service: 'backend'
}

export interface ExperimentListResponse {
  experiments: ExperimentResult[]
}
