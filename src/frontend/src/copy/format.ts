import type { Algorithm, HillClimbingVariant, Move, ObjectiveMode, PackagePlacement } from '../types/experiment'

/*
 * UI copy rules: no middle dots, no ellipses, and no em dashes anywhere in the
 * interface. Join fragments with commas or put them in separate elements.
 */

const decimal = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })
const whole = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

export function formatNumber(value: number): string {
  return decimal.format(value)
}

export function formatWhole(value: number): string {
  return whole.format(value)
}

/** Short value for charts and dense rows, keeping about three significant digits even for tiny values. */
export function formatCompact(value: number): string {
  if (value === 0) return '0'
  const magnitude = Math.abs(value)
  if (magnitude >= 1000) return whole.format(value)
  if (magnitude < 0.01) return String(Number(value.toPrecision(2)))
  return decimal.format(Number(value.toPrecision(3)))
}

export const ALGORITHM_LABELS: Record<Algorithm, string> = {
  hill_climbing: 'Hill Climbing',
  simulated_annealing: 'Simulated Annealing',
  genetic_algorithm: 'Genetic Algorithm',
}

export const ALGORITHM_SHORT_LABELS: Record<Algorithm, string> = {
  hill_climbing: 'Hill Climbing',
  simulated_annealing: 'Annealing',
  genetic_algorithm: 'Genetic',
}

export const VARIANT_LABELS: Record<HillClimbingVariant, string> = {
  steepest_ascent: 'Steepest ascent',
  stochastic: 'Stochastic',
  sideways: 'Sideways',
  random_restart: 'Random restart',
}

export const OBJECTIVE_LABELS: Record<ObjectiveMode, string> = {
  total_value: 'Total value',
  eta_weighted_value: 'ETA weighted',
}

export const ORIENTATION_NAMES = ['WLH', 'LWH', 'WHL', 'HWL', 'LHW', 'HLW'] as const

/** Turns a backend snake_case reason such as max_iterations into "Max iterations". */
export function humanize(reason: unknown): string {
  if (typeof reason !== 'string' || reason === '') return 'Not recorded'
  const text = reason.replaceAll('_', ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function placementText(placement: PackagePlacement): string {
  if (placement.truck_id === null || placement.position === null) return 'Dock, outside the fleet'
  const { x, y, z } = placement.position
  return `${placement.truck_id} at (${x}, ${y}, ${z})`
}

function where(truckId: string | null): string {
  return truckId ?? 'the Dock'
}

/** One plain sentence describing what a move did. */
export function describeMove(move: Move): string {
  const [first, second] = move.package_ids
  const before = move.before[0]
  const after = move.after[0]
  if (move.type === 'SWAP') return `${first} and ${second ?? 'another package'} swapped places`
  if (!before || !after) return `${move.type} on ${first}`
  if (move.type === 'ROTATE') {
    return `${first} rotated from ${ORIENTATION_NAMES[before.orientation]} to ${ORIENTATION_NAMES[after.orientation]} in ${where(after.truck_id)}`
  }
  if (before.truck_id === null && after.truck_id !== null) return `${first} loaded from the Dock into ${after.truck_id}`
  if (before.truck_id !== null && after.truck_id === null) return `${first} unloaded from ${before.truck_id} to the Dock`
  if (before.truck_id !== after.truck_id) return `${first} transferred from ${where(before.truck_id)} to ${where(after.truck_id)}`
  return `${first} moved inside ${where(after.truck_id)}`
}

/** Compact "from to" text for move lists. */
export function moveRoute(move: Move): string {
  const before = move.before[0]
  const after = move.after[0]
  if (!before || !after) return move.type
  if (move.type === 'ROTATE') return `${ORIENTATION_NAMES[before.orientation]} to ${ORIENTATION_NAMES[after.orientation]}`
  const name = (truckId: string | null) => truckId ?? 'Dock'
  if (move.type === 'SWAP') {
    const other = move.before[1]
    return other && other.truck_id !== before.truck_id ? `${name(before.truck_id)} with ${name(other.truck_id)}` : `within ${name(before.truck_id)}`
  }
  return `${name(before.truck_id)} to ${name(after.truck_id)}`
}
