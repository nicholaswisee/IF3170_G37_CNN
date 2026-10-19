import type { Orientation, PackageSpec, Position, Problem, TruckSpec } from '../types/experiment'

export type Vec3 = [number, number, number]

/**
 * Effective (w, l, h) for a placement orientation. Mirrors the backend's
 * get_oriented_dimensions for rendering only; the backend decides validity.
 */
export function getOrientedDimensions(pkg: PackageSpec, orientation: Orientation): Vec3 {
  const { width: w, length: l, height: h } = pkg
  const byOrientation: Vec3[] = [
    [w, l, h], // WLH
    [l, w, h], // LWH
    [w, h, l], // WHL
    [h, w, l], // HWL
    [l, h, w], // LHW
    [h, l, w], // HLW
  ]
  return byOrientation[orientation]
}

/*
 * The only backend -> Three.js conversion in the app.
 * Backend: x = width, y = depth, z = height, anchor = left-bottom-back corner.
 * Three.js: Y is vertical and meshes are positioned by their center.
 */

/** Box size in Three.js axes for backend dimensions (w, l, h). */
export function toThreeSize([w, l, h]: Vec3): Vec3 {
  return [w, h, l]
}

/** Three.js center of a box anchored at a backend position. */
export function toThreeCenter(position: Position, [w, l, h]: Vec3): Vec3 {
  return [position.x + w / 2, position.z + h / 2, position.y + l / 2]
}

export function truckToThree(truck: TruckSpec, offsetX = 0): { size: Vec3; center: Vec3 } {
  const dimensions: Vec3 = [truck.width, truck.length, truck.height]
  const [cx, cy, cz] = toThreeCenter({ x: 0, y: 0, z: 0 }, dimensions)
  return { size: toThreeSize(dimensions), center: [cx + offsetX, cy, cz] }
}

/*
 * Fleet layout. Trucks stand side by side along the
 * Three.js X axis in problem order with their back walls at depth 0. Outside
 * packages rest on a Dock in front of the fleet, one fixed slot per package.
 * Dock slots are a rendering layout only and never a backend position.
 */

export const TRUCK_GAP = 3
const DOCK_DISTANCE = 5
const DOCK_SLOT_MARGIN = 1.4

export interface DockLayout {
  originX: number
  originZ: number
  pitch: number
  columns: number
  rows: number
  width: number
  depth: number
}

export interface FleetLayout {
  /** Three.js X offset of each truck's back-left corner, keyed by truck ID. */
  offsets: Record<string, number>
  width: number
  maxLength: number
  maxHeight: number
  dock: DockLayout
}

export function layoutFleet(problem: Problem): FleetLayout {
  const offsets: Record<string, number> = {}
  let cursor = 0
  for (const truck of problem.trucks) {
    offsets[truck.id] = cursor
    cursor += truck.width + TRUCK_GAP
  }
  const width = Math.max(cursor - TRUCK_GAP, 0)
  const maxLength = Math.max(0, ...problem.trucks.map((truck) => truck.length))
  const maxHeight = Math.max(0, ...problem.trucks.map((truck) => truck.height))
  const largestSide = Math.max(1, ...problem.packages.map((pkg) => Math.max(pkg.width, pkg.length, pkg.height)))
  const pitch = largestSide + DOCK_SLOT_MARGIN
  const count = Math.max(problem.packages.length, 1)
  const columns = Math.max(Math.min(count, 3), Math.min(count, Math.floor((width + 2) / pitch)))
  const rows = Math.ceil(count / columns)
  return {
    offsets,
    width,
    maxLength,
    maxHeight,
    dock: {
      originX: width / 2 - (columns * pitch) / 2,
      originZ: maxLength + DOCK_DISTANCE,
      pitch,
      columns,
      rows,
      width: columns * pitch,
      depth: rows * pitch,
    },
  }
}

/** Center of a package's Dock slot on the ground plane, by package index. */
export function dockSlotCenter(dock: DockLayout, index: number): { x: number; z: number } {
  const column = index % dock.columns
  const row = Math.floor(index / dock.columns)
  return { x: dock.originX + (column + 0.5) * dock.pitch, z: dock.originZ + (row + 0.5) * dock.pitch }
}

/** Three.js center and size of one package, inside its truck or on its Dock slot. */
export function packageToThree(
  layout: FleetLayout,
  pkg: PackageSpec,
  index: number,
  truckId: string | null,
  position: Position | null,
  orientation: Orientation,
): { center: Vec3; size: Vec3 } {
  const dimensions = getOrientedDimensions(pkg, orientation)
  const size = toThreeSize(dimensions)
  const offset = truckId === null ? undefined : layout.offsets[truckId]
  if (offset === undefined || position === null) {
    const slot = dockSlotCenter(layout.dock, index)
    return { center: [slot.x, size[1] / 2, slot.z], size }
  }
  const [x, y, z] = toThreeCenter(position, dimensions)
  return { center: [x + offset, y, z], size }
}
