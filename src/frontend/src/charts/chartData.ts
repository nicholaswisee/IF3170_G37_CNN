import type { Algorithm, SearchEvent } from '../types/experiment'

/** Axis and replay label: GA counts generations, HC and SA count iterations (§61). */
export function progressLabel(algorithm: Algorithm | null | undefined): 'Generation' | 'Iteration' {
  return algorithm === 'genetic_algorithm' ? 'Generation' : 'Iteration'
}

export interface ObjectivePoint {
  iteration: number
  current: number
  best: number
  /** GA population mean; null for HC and SA. */
  mean: number | null
}

/** Objective series for every algorithm. For GA, current is the generation maximum. */
export function toObjectiveSeries(history: SearchEvent[]): ObjectivePoint[] {
  return history.map((event) => ({
    iteration: event.iteration,
    current: event.current_score,
    best: event.best_score,
    mean: event.mean_score,
  }))
}

export interface AnnealingPoint {
  iteration: number
  temperature: number | null
  probability: number | null
}

export function toAnnealingSeries(history: SearchEvent[]): AnnealingPoint[] {
  return history.map((event) => ({
    iteration: event.iteration,
    temperature: event.temperature,
    probability: event.acceptance_probability,
  }))
}

/** Iterations where Random Restart begins a new climb, read from event metadata. */
export function restartStarts(history: SearchEvent[]): number[] {
  const starts: number[] = []
  let previous: unknown
  for (const event of history) {
    const restart = event.metadata.restart
    if (typeof restart === 'number' && restart !== previous && previous !== undefined) starts.push(event.iteration)
    previous = restart
  }
  return starts
}

export interface RestartScore {
  restart: number
  score: number
}

/** Best score of each climb from run metadata, numbered from 1. */
export function bestScorePerRestart(metadata: Record<string, unknown>): RestartScore[] {
  const scores = metadata.best_score_per_restart
  if (!Array.isArray(scores)) return []
  return scores.flatMap((score, index) => typeof score === 'number' && Number.isFinite(score) ? [{ restart: index + 1, score }] : [])
}

/** History index for a stored view: the first event that reached the run's best score. */
export function bestEventIndex(history: SearchEvent[], bestScore: number): number {
  const index = history.findIndex((event) => Math.abs(event.current_score - bestScore) < 1e-9)
  return index >= 0 ? index : Math.max(history.length - 1, 0)
}
