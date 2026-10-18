import type { Limits, NumericRange, Problem } from '../types/experiment'

const numberText = new Intl.NumberFormat('en-US', { maximumFractionDigits: 6, useGrouping: false })

/** Smallest value the range accepts, given the step used to move below an exclusive bound. */
export function lowestValue(range: NumericRange, step: number): number | null {
  if (range.minimum !== null) return range.minimum
  if (range.exclusive_minimum === null) return null
  return range.integer ? Math.floor(range.exclusive_minimum) + 1 : range.exclusive_minimum + step
}

/** Largest value the range accepts, given the step used to stay below an exclusive bound. */
export function highestValue(range: NumericRange, step: number): number | null {
  if (range.maximum !== null && range.exclusive_maximum !== null) {
    return Math.min(range.maximum, highestValue({ ...range, maximum: null }, step) ?? range.maximum)
  }
  if (range.maximum !== null) return range.maximum
  if (range.exclusive_maximum === null) return null
  return range.integer ? Math.ceil(range.exclusive_maximum) - 1 : range.exclusive_maximum - step
}

/** A range is fixed when it allows exactly one value, such as GA elitism. */
export function isFixed(range: NumericRange): boolean {
  return range.minimum !== null && range.minimum === range.maximum
}

/** Plain sentence fragment describing the range, for field hints. */
export function describeRange(range: NumericRange): string {
  if (range.integer) {
    const low = lowestValue(range, 1)
    const high = highestValue(range, 1)
    if (low !== null && high !== null) return `${numberText.format(low)} to ${numberText.format(high)}`
    if (low !== null) return `${numberText.format(low)} or more`
    if (high !== null) return `Up to ${numberText.format(high)}`
    return 'Any whole number'
  }
  const parts: string[] = []
  if (range.minimum !== null) parts.push(`${numberText.format(range.minimum)} or more`)
  else if (range.exclusive_minimum !== null) parts.push(`above ${numberText.format(range.exclusive_minimum)}`)
  if (range.maximum !== null) parts.push(`up to ${numberText.format(range.maximum)}`)
  else if (range.exclusive_maximum !== null) parts.push(`below ${numberText.format(range.exclusive_maximum)}`)
  if (parts.length === 0) return 'Any number'
  if (range.minimum !== null && range.maximum !== null) {
    return `${numberText.format(range.minimum)} to ${numberText.format(range.maximum)}`
  }
  const text = parts.join(' and ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Returns an error sentence when the value falls outside the backend range, otherwise null. */
export function checkNumber(label: string, value: number | null, range: NumericRange): string | null {
  if (value === null) return range.nullable ? null : `${label} is required`
  if (!Number.isFinite(value)) return `${label} must be a number`
  if (range.integer && !Number.isSafeInteger(value)) return `${label} must be a whole number`
  const outside = (range.minimum !== null && value < range.minimum)
    || (range.exclusive_minimum !== null && value <= range.exclusive_minimum)
    || (range.maximum !== null && value > range.maximum)
    || (range.exclusive_maximum !== null && value >= range.exclusive_maximum)
  if (!outside) return null
  const allowed = describeRange(range)
  return `${label} must be ${allowed.charAt(0).toLowerCase()}${allowed.slice(1)}`
}

/** Checks the problem-wide limits that the per-field form cannot see. */
export function checkProblemLimits(problem: Problem, limits: Limits): string | null {
  const { max_trucks, max_packages, max_id_length, max_total_truck_volume } = limits.problem
  if (problem.trucks.length > max_trucks) return `A problem can have at most ${max_trucks} trucks`
  if (problem.packages.length > max_packages) return `A problem can have at most ${max_packages} packages`
  const longId = [...problem.trucks, ...problem.packages].find((item) => item.id.length > max_id_length)
  if (longId) return `ID ${longId.id.slice(0, 24)} is longer than ${max_id_length} characters`
  const volume = totalTruckVolume(problem)
  if (volume > max_total_truck_volume) {
    return `The trucks hold ${volume} cells in total. The backend allows up to ${max_total_truck_volume}`
  }
  return null
}

export function totalTruckVolume(problem: Problem): number {
  return problem.trucks.reduce((sum, truck) => sum + truck.width * truck.length * truck.height, 0)
}
