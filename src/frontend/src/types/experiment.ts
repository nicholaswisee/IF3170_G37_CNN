export type Algorithm = 'hill_climbing' | 'simulated_annealing' | 'genetic_algorithm'

export interface Position {
  x: number
  y: number
  z: number
}

export interface PackagePlacement {
  package_id: string
  position: Position
  orientation: 'horizontal' | 'vertical'
  inside: boolean
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
  objective_value: number
  total_weight: number
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
