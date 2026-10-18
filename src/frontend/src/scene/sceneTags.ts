import type { Intersection } from 'three'

/** userData attached to pickable meshes so one handler can resolve what the pointer is over. */
export type SceneTag =
  | { kind: 'package'; id: string; truckId: string | null }
  | { kind: 'truck'; id: string }
  | { kind: 'dock' }

export type SceneHit =
  | { kind: 'package'; id: string }
  | { kind: 'truck'; id: string }
  | { kind: 'dock' }

function tagOf(hit: Intersection): SceneTag | null {
  const tag = hit.object.userData as Partial<SceneTag>
  return tag.kind === 'package' || tag.kind === 'truck' || tag.kind === 'dock' ? tag as SceneTag : null
}

/**
 * What a click should act on. In free view a truck (or any package inside it)
 * locks the camera and Dock packages open their card. In a locked view only
 * packages of the locked truck are pickable, and another truck moves the lock.
 */
export function resolveClick(hits: Intersection[], lockedTruckId: string | null): SceneHit | null {
  for (const hit of hits) {
    const tag = tagOf(hit)
    if (!tag) continue
    if (tag.kind === 'package') {
      if (lockedTruckId === null) return tag.truckId === null ? { kind: 'package', id: tag.id } : { kind: 'truck', id: tag.truckId }
      if (tag.truckId === lockedTruckId) return { kind: 'package', id: tag.id }
      continue
    }
    if (tag.kind === 'truck') {
      if (tag.id === lockedTruckId) continue
      return { kind: 'truck', id: tag.id }
    }
    if (lockedTruckId === null) return { kind: 'dock' }
  }
  return null
}

/** The package the pointer is over, preferring packages behind transparent truck walls. */
export function resolveHoverPackage(hits: Intersection[], lockedTruckId: string | null): string | null {
  for (const hit of hits) {
    const tag = tagOf(hit)
    if (tag?.kind !== 'package') continue
    if (lockedTruckId === null || tag.truckId === lockedTruckId) return tag.id
  }
  return null
}
