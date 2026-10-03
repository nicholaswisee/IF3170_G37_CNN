import type { Orientation, PackageSpec, Position, TruckSpec } from '../types/experiment'

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
 * The only backend -> Three.js conversion in the app (Architecture Freeze §63).
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

export function truckToThree(truck: TruckSpec): { size: Vec3; center: Vec3 } {
  const dimensions: Vec3 = [truck.width, truck.length, truck.height]
  return {
    size: toThreeSize(dimensions),
    center: toThreeCenter({ x: 0, y: 0, z: 0 }, dimensions),
  }
}
