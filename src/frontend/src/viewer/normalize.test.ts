import assert from 'node:assert/strict'
import test from 'node:test'
import { getOrientedDimensions, toThreeCenter, toThreeSize, truckToThree } from './geometry'
import { normalizeViewerState } from './normalize'
import type { OptimizationState, Problem } from '../types/experiment'

const problem: Problem = {
  trucks: [
    { id: 'T1', width: 10, length: 8, height: 6, max_capacity: 100 },
    { id: 'T2', width: 4, length: 4, height: 3, max_capacity: 20 },
    { id: 'T3', width: 2, length: 2, height: 2, max_capacity: 5 },
  ],
  packages: [
    { id: 'A', width: 4, length: 3, height: 2, value: 40, weight: 20, is_fragile: false, eta: 2 },
    { id: 'B', width: 2, length: 2, height: 1, value: 25, weight: 5, is_fragile: true, eta: 0 },
    { id: 'C', width: 3, length: 1, height: 2, value: 10, weight: 4, is_fragile: false, eta: 3 },
    { id: 'D', width: 1, length: 1, height: 1, value: 8, weight: 2, is_fragile: true, eta: 1 },
  ],
}

const state: OptimizationState = {
  placements: [
    { package_id: 'A', truck_id: 'T1', position: { x: 0, y: 0, z: 0 }, orientation: 1 },
    { package_id: 'B', truck_id: 'T2', position: { x: 1, y: 2, z: 0 }, orientation: 0 },
    { package_id: 'C', truck_id: null, position: null, orientation: 3 },
    { package_id: 'D', truck_id: 'T1', position: null, orientation: 0 },
  ],
}

test('groups packages by truck and keeps every truck, including empty ones', () => {
  const viewer = normalizeViewerState(problem, state)
  assert.deepEqual(viewer.trucks.map((truck) => truck.id), ['T1', 'T2', 'T3'])
  assert.deepEqual(viewer.trucks.map((truck) => truck.packages.map((pkg) => pkg.id)), [['A'], ['B'], []])
  assert.deepEqual(viewer.trucks[1].dimensions, [4, 4, 3])
  assert.equal(viewer.trucks[1].maxCapacity, 20)
})

test('lists outside packages without a coordinate, even when a truck id is set', () => {
  const viewer = normalizeViewerState(problem, state)
  assert.deepEqual(viewer.outside.map((pkg) => pkg.id), ['C', 'D'])
  for (const pkg of viewer.outside) {
    assert.equal(pkg.position, null)
    assert.equal(pkg.truckId, null)
  }
  const [c] = viewer.outside
  assert.deepEqual(
    { value: c.value, weight: c.weight, eta: c.eta, isFragile: c.isFragile, originalDimensions: c.originalDimensions },
    { value: 10, weight: 4, eta: 3, isFragile: false, originalDimensions: [3, 1, 2] },
  )
})

test('uses oriented dimensions as effective dimensions', () => {
  const [a] = normalizeViewerState(problem, state).trucks[0].packages
  assert.deepEqual(a.originalDimensions, [4, 3, 2])
  assert.deepEqual(a.effectiveDimensions, [3, 4, 2])
  assert.equal(a.orientation, 1)
})

test('skips placements that name unknown packages or trucks', () => {
  const viewer = normalizeViewerState(problem, {
    placements: [
      { package_id: 'ghost', truck_id: 'T1', position: { x: 0, y: 0, z: 0 }, orientation: 0 },
      { package_id: 'A', truck_id: 'missing', position: { x: 0, y: 0, z: 0 }, orientation: 0 },
    ],
  })
  assert.deepEqual(viewer.trucks.flatMap((truck) => truck.packages), [])
  assert.deepEqual(viewer.outside, [])
})

test('an empty state renders empty trucks and no outside packages', () => {
  const viewer = normalizeViewerState(problem, { placements: [] })
  assert.equal(viewer.trucks.length, 3)
  assert.ok(viewer.trucks.every((truck) => truck.packages.length === 0))
  assert.deepEqual(viewer.outside, [])
})

test('oriented dimensions cover all six orientations', () => {
  const pkg = problem.packages[0]
  const expected = [[4, 3, 2], [3, 4, 2], [4, 2, 3], [2, 4, 3], [3, 2, 4], [2, 3, 4]]
  for (const [orientation, dimensions] of expected.entries()) {
    assert.deepEqual(getOrientedDimensions(pkg, orientation as 0 | 1 | 2 | 3 | 4 | 5), dimensions)
  }
})

test('maps backend (x=width, y=depth, z=height) to Three.js Y-up centers', () => {
  assert.deepEqual(toThreeSize([4, 3, 2]), [4, 2, 3])
  assert.deepEqual(toThreeCenter({ x: 1, y: 2, z: 5 }, [4, 3, 2]), [1 + 2, 5 + 1, 2 + 1.5])
  assert.deepEqual(truckToThree(problem.trucks[1]), { size: [4, 3, 4], center: [2, 1.5, 2] })
})
