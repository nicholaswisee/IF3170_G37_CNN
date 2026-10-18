import { Line } from '@react-three/drei'
import { useEffect, useMemo } from 'react'
import { ExtrudeGeometry, Shape, Vector3 } from 'three'
import { palette } from '../theme'
import type { DockLayout } from '../viewer/geometry'
import type { SceneTag } from './sceneTags'

function roundedRectangle(width: number, depth: number, radius: number): Shape {
  const shape = new Shape()
  shape.moveTo(radius, 0)
  shape.lineTo(width - radius, 0)
  shape.quadraticCurveTo(width, 0, width, radius)
  shape.lineTo(width, depth - radius)
  shape.quadraticCurveTo(width, depth, width - radius, depth)
  shape.lineTo(radius, depth)
  shape.quadraticCurveTo(0, depth, 0, depth - radius)
  shape.lineTo(0, radius)
  shape.quadraticCurveTo(0, 0, radius, 0)
  return shape
}

/** Staging pad in front of the fleet where outside packages wait. It is never a truck position. Its label lives in SceneLabels. */
export function DockArea({ dock }: { dock: DockLayout }) {
  const pad = 0.6
  const slab = useMemo(() => new ExtrudeGeometry(roundedRectangle(dock.width + pad * 2, dock.depth + pad * 2, 1.4), { depth: 0.3, bevelEnabled: false }), [dock.width, dock.depth])
  useEffect(() => () => slab.dispose(), [slab])
  const outline = useMemo(() => roundedRectangle(dock.width + 0.4, dock.depth + 0.4, 1.1).getPoints(12)
    .map((point) => new Vector3(dock.originX - 0.2 + point.x, 0.02, dock.originZ - 0.2 + point.y)), [dock])
  const tag: SceneTag = { kind: 'dock' }

  return (
    <group>
      <mesh geometry={slab} rotation={[Math.PI / 2, 0, 0]} position={[dock.originX - pad, 0, dock.originZ - pad]} receiveShadow userData={tag}>
        <meshStandardMaterial color={palette.dockFloor} roughness={0.95} />
      </mesh>
      <Line points={outline} color={palette.dockEdge} dashed dashSize={0.6} gapSize={0.4} lineWidth={1.2} />
    </group>
  )
}
