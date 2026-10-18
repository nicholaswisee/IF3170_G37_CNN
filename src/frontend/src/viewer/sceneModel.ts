import type { OptimizationState, Orientation, PackagePlacement, PackageSpec, Problem } from '../types/experiment'
import { packageToThree, type FleetLayout, type Vec3 } from './geometry'

export interface ScenePackage {
  id: string
  index: number
  spec: PackageSpec
  /** Truck the package is loaded in; null when it waits on the Dock. */
  truckId: string | null
  placement: PackagePlacement
  center: Vec3
  size: Vec3
}

function outsidePlacement(packageId: string): PackagePlacement {
  return { package_id: packageId, truck_id: null, position: null, orientation: 0 }
}

/**
 * Every problem package with its Three.js transform for one state. A package
 * without a usable truck placement is shown on its Dock slot. This never
 * judges feasibility; the backend owns validity.
 */
export function buildScenePackages(problem: Problem, state: OptimizationState, layout: FleetLayout): ScenePackage[] {
  const placements = new Map(state.placements.map((placement) => [placement.package_id, placement]))
  return problem.packages.map((spec, index) => {
    const placement = placements.get(spec.id) ?? outsidePlacement(spec.id)
    const loaded = placement.truck_id !== null && placement.position !== null && layout.offsets[placement.truck_id] !== undefined
    const truckId = loaded ? placement.truck_id : null
    const { center, size } = packageToThree(layout, spec, index, truckId, loaded ? placement.position : null, placement.orientation as Orientation)
    return { id: spec.id, index, spec, truckId, placement, center, size }
  })
}

/** Packages without a truck placement in a state, including any the state does not mention. */
export function outsidePackages(problem: Problem, state: OptimizationState): { pkg: PackageSpec; index: number; placement: PackagePlacement | undefined }[] {
  const placements = new Map(state.placements.map((placement) => [placement.package_id, placement]))
  return problem.packages
    .map((pkg, index) => ({ pkg, index, placement: placements.get(pkg.id) }))
    .filter(({ placement }) => !placement || placement.truck_id === null || placement.position === null)
}

export interface TruckLoad {
  weight: number
  count: number
  value: number
}

/** Weight, count, and value per truck, summed from the placements of one state. */
export function truckLoads(problem: Problem, state: OptimizationState): Record<string, TruckLoad> {
  const specs = new Map(problem.packages.map((pkg) => [pkg.id, pkg]))
  const loads: Record<string, TruckLoad> = Object.fromEntries(problem.trucks.map((truck) => [truck.id, { weight: 0, count: 0, value: 0 }]))
  for (const placement of state.placements) {
    const spec = specs.get(placement.package_id)
    const load = placement.truck_id === null ? undefined : loads[placement.truck_id]
    if (!spec || !load) continue
    load.weight += spec.weight
    load.count += 1
    load.value += spec.value
  }
  return loads
}

function samePlacement(a: PackagePlacement | undefined, b: PackagePlacement): boolean {
  return a !== undefined
    && a.truck_id === b.truck_id
    && a.orientation === b.orientation
    && a.position?.x === b.position?.x
    && a.position?.y === b.position?.y
    && a.position?.z === b.position?.z
}

/** Package IDs whose placement differs between two states, in the order of the newer state. */
export function changedPackageIds(previous: OptimizationState | null, next: OptimizationState): string[] {
  if (!previous) return []
  const before = new Map(previous.placements.map((placement) => [placement.package_id, placement]))
  return next.placements.filter((placement) => !samePlacement(before.get(placement.package_id), placement)).map((placement) => placement.package_id)
}

/**
 * Peak height added to a package's path when it changes trucks or crosses to
 * the Dock, so it travels over the truck walls instead of through them.
 */
export function arcHeight(from: Vec3, to: Vec3, tallestTruck: number): number {
  const distance = Math.hypot(to[0] - from[0], to[1] - from[1], to[2] - from[2])
  return Math.max(tallestTruck + 2.5 - (from[1] + to[1]) / 2, distance * 0.22, 2.5)
}

/** Point along a transfer path at progress t in [0, 1]. */
export function arcPoint(from: Vec3, to: Vec3, arc: number, t: number): Vec3 {
  return [
    from[0] + (to[0] - from[0]) * t,
    from[1] + (to[1] - from[1]) * t + Math.sin(Math.PI * t) * arc,
    from[2] + (to[2] - from[2]) * t,
  ]
}

export interface Frame {
  center: Vec3
  radius: number
}

export function truckFrame(layout: FleetLayout, truck: { id: string; width: number; length: number; height: number }): Frame {
  const offset = layout.offsets[truck.id] ?? 0
  return {
    center: [offset + truck.width / 2, truck.height * 0.45, truck.length / 2],
    radius: 0.5 * Math.hypot(truck.width, truck.height, truck.length),
  }
}

export function fleetFrame(layout: FleetLayout): Frame {
  const { dock } = layout
  const minX = Math.min(0, dock.originX)
  const maxX = Math.max(layout.width, dock.originX + dock.width)
  const maxZ = dock.originZ + dock.depth
  return {
    center: [(minX + maxX) / 2, layout.maxHeight * 0.25, maxZ / 2],
    radius: 0.5 * Math.hypot(maxX - minX, layout.maxHeight, maxZ),
  }
}

export function dockFrame(layout: FleetLayout): Frame {
  const { dock } = layout
  return {
    center: [dock.originX + dock.width / 2, 0, dock.originZ + dock.depth / 2],
    radius: 0.5 * Math.hypot(dock.width, dock.depth),
  }
}

export type ColorMode = 'identity' | 'value' | 'eta' | 'fragile'

const IDENTITY_PALETTE = ['#8cc8ff', '#a3e4b7', '#ffcf94', '#c9bdff', '#ffb7c4', '#94dfe8', '#ffe08f', '#b9da97', '#f3bce6', '#adc6ff', '#ffc3a1', '#9fd8cf']
const FRAGILE_COLOR = '#ff8f94'
const MUTED_COLOR = '#dde2ea'

function mixHex(from: string, to: string, amount: number): string {
  const channel = (hex: string, index: number) => parseInt(hex.slice(1 + index * 2, 3 + index * 2), 16)
  const mixed = [0, 1, 2].map((index) => Math.round(channel(from, index) + (channel(to, index) - channel(from, index)) * amount))
  return `#${mixed.map((value) => value.toString(16).padStart(2, '0')).join('')}`
}

function normalized(values: number[], value: number): number {
  const low = Math.min(...values)
  const high = Math.max(...values)
  return high > low ? (value - low) / (high - low) : 0.5
}

/** Display color of a package for the chosen Layers color mode. */
export function packageColor(problem: Problem, index: number, mode: ColorMode): string {
  const pkg = problem.packages[index]
  if (!pkg) return MUTED_COLOR
  switch (mode) {
    case 'identity':
      return pkg.is_fragile ? FRAGILE_COLOR : IDENTITY_PALETTE[index % IDENTITY_PALETTE.length]
    case 'value':
      return mixHex('#e3eeff', '#2f7cf0', normalized(problem.packages.map((item) => item.value), pkg.value))
    case 'eta':
      // Urgent packages (low ETA) get the strongest color.
      return mixHex('#ff9a3c', '#fff0dc', normalized(problem.packages.map((item) => item.eta), pkg.eta))
    case 'fragile':
      return pkg.is_fragile ? FRAGILE_COLOR : MUTED_COLOR
  }
}
