import type { SearchEvent } from '../types/experiment'

export function toAnnealingChartData(history: SearchEvent[]) {
  return history.map((event) => ({
    iteration: event.iteration,
    current: event.current_score,
    best: event.best_score,
    temperature: event.temperature,
    probability: event.acceptance_probability,
  }))
}
