import assert from 'node:assert/strict'
import test from 'node:test'
import type { Intersection } from 'three'
import { resolveClick, resolveHoverPackage, type SceneTag } from './sceneTags'

function hits(...tags: (SceneTag | Record<string, never>)[]): Intersection[] {
  return tags.map((userData) => ({ object: { userData } }) as unknown as Intersection)
}

const wallA: SceneTag = { kind: 'truck', id: 'A' }
const wallB: SceneTag = { kind: 'truck', id: 'B' }
const insideA: SceneTag = { kind: 'package', id: 'P1', truckId: 'A' }
const insideB: SceneTag = { kind: 'package', id: 'P2', truckId: 'B' }
const onDock: SceneTag = { kind: 'package', id: 'P3', truckId: null }

test('in free view a click on a truck or a package inside it locks that truck', () => {
  assert.deepEqual(resolveClick(hits(wallA, insideA), null), { kind: 'truck', id: 'A' })
  assert.deepEqual(resolveClick(hits(insideB), null), { kind: 'truck', id: 'B' })
  assert.deepEqual(resolveClick(hits(onDock), null), { kind: 'package', id: 'P3' })
  assert.deepEqual(resolveClick(hits({ kind: 'dock' }), null), { kind: 'dock' })
  assert.equal(resolveClick(hits({}), null), null)
})

test('in a locked view clicks pass through the locked walls to its packages', () => {
  assert.deepEqual(resolveClick(hits(wallA, insideA), 'A'), { kind: 'package', id: 'P1' })
  assert.equal(resolveClick(hits(wallA), 'A'), null)
})

test('in a locked view other trucks move the lock and their packages and the Dock are ignored', () => {
  assert.deepEqual(resolveClick(hits(wallB, insideB), 'A'), { kind: 'truck', id: 'B' })
  assert.equal(resolveClick(hits(insideB, onDock, { kind: 'dock' }), 'A'), null)
})

test('hover prefers packages behind glass walls and respects the lock', () => {
  assert.equal(resolveHoverPackage(hits(wallA, insideA), null), 'P1')
  assert.equal(resolveHoverPackage(hits(wallB, insideB, insideA), 'A'), 'P1')
  assert.equal(resolveHoverPackage(hits(wallB, insideB), 'A'), null)
})
