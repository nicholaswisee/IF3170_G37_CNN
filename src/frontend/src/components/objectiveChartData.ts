import type { Algorithm, SearchEvent } from '../types/experiment'

export function progressLabelForAlgorithm(algorithm: Algorithm | null | undefined): 'Generation' | 'Iteration' {
  return algorithm === 'genetic_algorithm' ? 'Generation' : 'Iteration'
}

export function toObjectiveChartData(history: SearchEvent[], algorithm: Algorithm) {
  return history.map((event) => ({
    generation: event.iteration,
    maximum: event.current_score,
    mean: algorithm === 'genetic_algorithm' ? event.mean_score : null,
  }))
}
