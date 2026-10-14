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

export interface GeneticAlgorithmInput {
  population_size: number
  generations: number
  crossover_probability: number
  mutation_probability: number
  seed: number
}

export function validateSeed(seed: number): string | null {
  return Number.isSafeInteger(seed)
    ? null
    : `Seed must be a safe integer (${Number.MIN_SAFE_INTEGER} to ${Number.MAX_SAFE_INTEGER}).`
}

export function validateGeneticAlgorithmInput(input: GeneticAlgorithmInput): string | null {
  if (!Number.isInteger(input.population_size) || input.population_size < 2 || input.population_size > 100) {
    return 'Population size must be an integer from 2 to 100.'
  }
  if (!Number.isInteger(input.generations) || input.generations < 1 || input.generations > 200) {
    return 'Generations must be an integer from 1 to 200.'
  }
  if (!Number.isFinite(input.crossover_probability) || input.crossover_probability < 0 || input.crossover_probability > 1) {
    return 'Crossover probability must be between 0 and 1.'
  }
  if (!Number.isFinite(input.mutation_probability) || input.mutation_probability < 0 || input.mutation_probability > 1) {
    return 'Mutation probability must be between 0 and 1.'
  }
  return validateSeed(input.seed)
}

export function validateSimulatedAnnealingInput(input: SimulatedAnnealingParameters & { seed: number }): string | null {
  if (input.initial_temperature !== null && (!Number.isFinite(input.initial_temperature) || input.initial_temperature <= 0)) {
    return 'Initial temperature must be positive, or empty for automatic temperature.'
  }
  if (!Number.isFinite(input.alpha) || input.alpha <= 0 || input.alpha >= 1) {
    return 'Alpha must be greater than 0 and less than 1.'
  }
  if (!Number.isFinite(input.min_temperature) || input.min_temperature <= 0) {
    return 'Minimum temperature must be positive.'
  }
  if (!Number.isInteger(input.max_iterations) || input.max_iterations < 1 || input.max_iterations > 5000) {
    return 'Maximum iterations must be an integer from 1 to 5000.'
  }
  if (!Number.isSafeInteger(input.stuck_patience) || input.stuck_patience < 1) {
    return 'Stuck patience must be a positive safe integer.'
  }
  return validateSeed(input.seed)
}

interface RunRequestOptions {
  algorithm: Algorithm
  problem: Problem
  seed: number
  objectiveMode?: ObjectiveMode
  variant?: HillClimbingVariant
  includeStateHistory?: boolean
  persist?: boolean
  geneticAlgorithmParameters?: Partial<GeneticAlgorithmParameters>
  simulatedAnnealingParameters?: Partial<SimulatedAnnealingParameters>
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
  geneticAlgorithmParameters,
  simulatedAnnealingParameters,
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
      return { ...common, algorithm, parameters: { ...defaultSimulatedAnnealingParameters, ...simulatedAnnealingParameters } }
    case 'genetic_algorithm':
      return {
        ...common,
        algorithm,
        parameters: {
          ...defaultGeneticAlgorithmParameters,
          ...geneticAlgorithmParameters,
          elite_count: 1,
        },
      }
  }
}
