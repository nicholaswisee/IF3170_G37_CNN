import assert from 'node:assert/strict'
import test from 'node:test'
import type { OptimizationState, Problem } from '../types/experiment'
import { TRUCK_GAP, dockSlotCenter, layoutFleet, packageToThree } from './geometry'
import { arcHeight, arcPoint, buildScenePackages, changedPackageIds, fleetFrame, packageColor, truckFrame, truckLoads } from './sceneModel'

const problem: Problem = {
  trucks: [
    { id: 'A', width: 8, length: 10, height: 6, max_capacity: 100 },
    { id: 'B', width: 4, length: 6, height: 3, max_capacity: 20 },
  ],
  packages: [
    { id: 'P1', width: 2, length: 3, height: 1, value: 40, weight: 20, is_fragile: false, eta: 2 },
    { id: 'P2', width: 1, length: 1, height: 1, value: 10, weight: 5, is_fragile: true, eta: 0 },
    { id: 'P3', width: 3, length: 1, height: 2, value: 25, weight: 7, is_fragile: false, eta: 5 },
  ],
}

const state: OptimizationState = {
  placements: [
    { package_id: 'P1', truck_id: 'A', position: { x: 1, y: 2, z: 0 }, orientation: 1 },
    { package_id: 'P2', truck_id: 'B', position: { x: 0, y: 0, z: 0 }, orientation: 0 },
    { package_id: 'P3', truck_id: null, position: null, orientation: 0 },
  ],
}

test('places trucks side by side in problem order with a fixed gap', () => {
  const layout = layoutFleet(problem)
  assert.deepEqual(layout.offsets, { A: 0, B: 8 + TRUCK_GAP })
  assert.equal(layout.width, 8 + TRUCK_GAP + 4)
  assert.equal(layout.maxLength, 10)
  assert.equal(layout.maxHeight, 6)
})

test('puts the Dock in front of every truck with one slot per package', () => {
  const { dock, maxLength } = layoutFleet(problem)
  assert.ok(dock.originZ > maxLength, 'the Dock never overlaps a truck')
  assert.ok(dock.columns * dock.rows >= problem.packages.length)
  const slots = problem.packages.map((_, index) => dockSlotCenter(dock, index))
  assert.equal(new Set(slots.map((slot) => `${slot.x},${slot.z}`)).size, slots.length)
})

test('maps loaded packages into their truck and outside packages onto the Dock', () => {
  const layout = layoutFleet(problem)
  const [p1, p2, p3] = buildScenePackages(problem, state, layout)
  // LWH turns 2x3x1 into 3x2x1; Three.js uses (w, h, l).
  assert.deepEqual(p1.size, [3, 1, 2])
  assert.deepEqual(p1.center, [1 + 1.5, 0.5, 2 + 1])
  assert.equal(p2.center[0], layout.offsets.B + 0.5)
  assert.equal(p3.truckId, null)
  const slot = dockSlotCenter(layout.dock, 2)
  assert.deepEqual(p3.center, [slot.x, 1, slot.z])
  assert.deepEqual(packageToThree(layout, problem.packages[2], 2, 'missing', { x: 0, y: 0, z: 0 }, 0).center, [slot.x, 1, slot.z])
})

test('packages missing from a state or pointing at unknown trucks wait on the Dock', () => {
  const layout = layoutFleet(problem)
  const items = buildScenePackages(problem, { placements: [{ package_id: 'P1', truck_id: 'ghost', position: { x: 0, y: 0, z: 0 }, orientation: 0 }] }, layout)
  assert.equal(items.length, 3)
  assert.ok(items.every((item) => item.truckId === null))
})

test('sums weight, count, and value per truck from the shown state', () => {
  assert.deepEqual(truckLoads(problem, state), {
    A: { weight: 20, count: 1, value: 40 },
    B: { weight: 5, count: 1, value: 10 },
  })
})

test('detects which packages changed between two states', () => {
  const next: OptimizationState = {
    placements: [
      { ...state.placements[0], orientation: 0 },
      state.placements[1],
      { package_id: 'P3', truck_id: 'B', position: { x: 1, y: 0, z: 0 }, orientation: 0 },
    ],
  }
  assert.deepEqual(changedPackageIds(state, next), ['P1', 'P3'])
  assert.deepEqual(changedPackageIds(null, next), [])
  assert.deepEqual(changedPackageIds(state, state), [])
})

test('transfer arcs clear the tallest truck and start and end on the placements', () => {
  const from: [number, number, number] = [0, 0.5, 0]
  const to: [number, number, number] = [20, 0.5, 0]
  const arc = arcHeight(from, to, 6)
  assert.ok(0.5 + arc >= 6 + 2, 'the peak passes above the walls')
  assert.deepEqual(arcPoint(from, to, arc, 0), from)
  assert.deepEqual(arcPoint(from, to, arc, 1).map((value) => Math.round(value * 1e9) / 1e9), to)
})

test('frames cover the locked truck and the whole fleet', () => {
  const layout = layoutFleet(problem)
  const b = truckFrame(layout, problem.trucks[1])
  assert.equal(b.center[0], layout.offsets.B + 2)
  assert.ok(fleetFrame(layout).radius > truckFrame(layout, problem.trucks[0]).radius)
})

test('color modes highlight fragile packages, value, and urgency', () => {
  assert.notEqual(packageColor(problem, 0, 'identity'), packageColor(problem, 1, 'identity'))
  assert.equal(packageColor(problem, 0, 'fragile'), packageColor(problem, 2, 'fragile'), 'non-fragile packages share the muted color')
  assert.notEqual(packageColor(problem, 1, 'fragile'), packageColor(problem, 0, 'fragile'))
  assert.equal(packageColor(problem, 0, 'value'), '#2f7cf0', 'highest value gets the strongest blue')
  assert.equal(packageColor(problem, 1, 'eta'), '#ff9a3c', 'lowest ETA gets the strongest orange')
  for (const mode of ['identity', 'value', 'eta', 'fragile'] as const) {
    for (const index of [0, 1, 2]) assert.match(packageColor(problem, index, mode), /^#[0-9a-f]{6}$/)
  }
})
