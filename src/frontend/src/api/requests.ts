import type {
  Algorithm,
  GeneticAlgorithmParameters,
  HillClimbingParameters,
  HillClimbingVariant,
  ObjectiveMode,
  Problem,
  RunExperimentRequest,
  SimulatedAnnealingParameters,
} from '../types/experiment'

// Frozen backend defaults (architecture freeze sections 27, 32, 36).
export const defaultHillClimbingParameters: HillClimbingParameters = {
  max_iterations: 2000,
  candidates_per_iteration: 50,
  max_sideways: 100,
  max_restarts: 10,
}

export const defaultSimulatedAnnealingParameters: SimulatedAnnealingParameters = {
  initial_temperature: null,
  alpha: 0.995,
  min_temperature: 0.001,
  max_iterations: 5000,
  stuck_patience: 50,
}

export const defaultGeneticAlgorithmParameters: GeneticAlgorithmParameters = {
  population_size: 50,
  generations: 100,
  crossover_probability: 0.8,
  mutation_probability: 0.2,
  elite_count: 1,
}

interface RunRequestOptions {
  algorithm: Algorithm
  problem: Problem
  seed: number
  objectiveMode?: ObjectiveMode
  variant?: HillClimbingVariant
  includeStateHistory?: boolean
  persist?: boolean
}

/** Build a single-run request with the full problem and default typed parameters. */
export function buildRunRequest({
  algorithm,
  problem,
  seed,
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
      return { ...common, algorithm, variant, parameters: { ...defaultHillClimbingParameters } }
    case 'simulated_annealing':
      return { ...common, algorithm, parameters: { ...defaultSimulatedAnnealingParameters } }
    case 'genetic_algorithm':
      return { ...common, algorithm, parameters: { ...defaultGeneticAlgorithmParameters } }
  }
}
