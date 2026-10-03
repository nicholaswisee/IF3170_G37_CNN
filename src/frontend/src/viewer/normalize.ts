import type { OptimizationState, Orientation, Position, Problem } from '../types/experiment'
import { getOrientedDimensions, type Vec3 } from './geometry'

export interface ViewerPackage {
  id: string
  truckId: string | null
  /** Backend anchor; null exactly when the package is outside the fleet. */
  position: Position | null
  originalDimensions: Vec3
  effectiveDimensions: Vec3
  orientation: Orientation
  value: number
  weight: number
  isFragile: boolean
  eta: number
}

export interface ViewerTruck {
  id: string
  /** Backend (width, length, height). */
  dimensions: Vec3
  maxCapacity: number
  packages: ViewerPackage[]
}

export interface ViewerState {
  trucks: ViewerTruck[]
  outside: ViewerPackage[]
}

/**
 * Group a state's placements by truck for rendering. Outside packages are kept
 * in a separate list and never given a coordinate. This does not judge
 * feasibility; placements naming unknown packages or trucks are skipped.
 */
export function normalizeViewerState(problem: Problem, state: OptimizationState): ViewerState {
  const packagesById = new Map(problem.packages.map((pkg) => [pkg.id, pkg]))
  const trucks: ViewerTruck[] = problem.trucks.map((truck) => ({
    id: truck.id,
    dimensions: [truck.width, truck.length, truck.height],
    maxCapacity: truck.max_capacity,
    packages: [],
  }))
  const trucksById = new Map(trucks.map((truck) => [truck.id, truck]))
  const outside: ViewerPackage[] = []

  for (const placement of state.placements) {
    const pkg = packagesById.get(placement.package_id)
    if (!pkg) continue

    const viewerPackage: ViewerPackage = {
      id: pkg.id,
      truckId: placement.truck_id,
      position: placement.position,
      originalDimensions: [pkg.width, pkg.length, pkg.height],
      effectiveDimensions: getOrientedDimensions(pkg, placement.orientation),
      orientation: placement.orientation,
      value: pkg.value,
      weight: pkg.weight,
      isFragile: pkg.is_fragile,
      eta: pkg.eta,
    }

    if (placement.truck_id === null || placement.position === null) {
      outside.push({ ...viewerPackage, truckId: null, position: null })
    } else {
      trucksById.get(placement.truck_id)?.packages.push(viewerPackage)
    }
  }

  return { trucks, outside }
}
