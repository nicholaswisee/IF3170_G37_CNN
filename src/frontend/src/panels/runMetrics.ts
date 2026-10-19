import { progressLabel } from '../charts/chartData'
import { formatCompact, formatWhole, humanize } from '../copy/format'
import type { ExperimentResult } from '../types/experiment'

function numberAt(metadata: Record<string, unknown>, key: string): number | null {
  const value = metadata[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** Label and value rows summarising a run, including the algorithm specific metadata (§48). */
export function runMetrics(experiment: ExperimentResult): [string, string][] {
  const { metadata } = experiment
  const rows: [string, string][] = [
    ['Runtime', `${formatWhole(experiment.runtime_ms)} ms`],
    [`${progressLabel(experiment.algorithm)}s`, formatWhole(experiment.iterations)],
    ['Stopped because', humanize(metadata.termination_reason)],
  ]
  const optional: [string, string, (value: number) => string][] = [
    ['sampled_neighbors', 'Sampled neighbors', formatWhole],
    ['sideways_moves', 'Sideways moves', formatWhole],
    ['restarts_performed', 'Restarts performed', formatWhole],
    ['stuck_events', 'Stuck events', formatWhole],
    ['final_temperature', 'Final temperature', formatCompact],
    ['population_size', 'Population size', formatWhole],
  ]
  for (const [key, label, format] of optional) {
    const value = numberAt(metadata, key)
    if (value !== null) rows.push([label, format(value)])
  }
  const perRestart = metadata.iterations_per_restart
  if (Array.isArray(perRestart) && perRestart.every((value) => typeof value === 'number')) {
    rows.push(['Iterations per restart', perRestart.join(', ')])
  }
  if (typeof metadata.persisted === 'boolean') rows.push(['Saved to output', metadata.persisted ? 'Yes' : 'No'])
  return rows
}

/** Number of packages loaded in a state. */
export function loadedCount(state: ExperimentResult['best_state']): number {
  return state.placements.filter((placement) => placement.truck_id !== null).length
}
