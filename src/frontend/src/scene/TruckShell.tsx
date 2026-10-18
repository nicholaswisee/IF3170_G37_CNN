import { useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import { BoxGeometry, DoubleSide, EdgesGeometry, type LineBasicMaterial, type MeshStandardMaterial } from 'three'
import { palette } from '../theme'
import type { TruckSpec } from '../types/experiment'
import type { SceneTag } from './sceneTags'

const noRaycast = () => null

interface TruckShellProps {
  truck: TruckSpec
  offset: number
  dimmed: boolean
}

/** Glass container walls and floor slab for one truck. Its floating label lives in SceneLabels. */
export function TruckShell({ truck, offset, dimmed }: TruckShellProps) {
  const { width, length, height } = truck
  const walls = useRef<MeshStandardMaterial>(null)
  const outline = useRef<LineBasicMaterial>(null)
  const wallGeometry = useMemo(() => new BoxGeometry(width, height, length), [width, height, length])
  const edgeGeometry = useMemo(() => new EdgesGeometry(wallGeometry), [wallGeometry])
  useEffect(() => () => {
    wallGeometry.dispose()
    edgeGeometry.dispose()
  }, [wallGeometry, edgeGeometry])

  useFrame((_, delta) => {
    const blend = Math.min(1, delta * 9)
    if (walls.current) walls.current.opacity += ((dimmed ? 0.05 : 0.15) - walls.current.opacity) * blend
    if (outline.current) outline.current.opacity += ((dimmed ? 0.18 : 0.6) - outline.current.opacity) * blend
  })

  const tag: SceneTag = { kind: 'truck', id: truck.id }
  return (
    <group position={[offset, 0, 0]}>
      <mesh position={[width / 2, -0.15, length / 2]} receiveShadow raycast={noRaycast}>
        <boxGeometry args={[width + 0.5, 0.3, length + 0.5]} />
        <meshStandardMaterial color={palette.truckFloor} roughness={0.9} />
      </mesh>
      <mesh geometry={wallGeometry} position={[width / 2, height / 2, length / 2]} userData={tag} renderOrder={2}>
        <meshStandardMaterial ref={walls} color={palette.truckWall} transparent opacity={0.15} depthWrite={false} side={DoubleSide} roughness={0.2} />
      </mesh>
      <lineSegments geometry={edgeGeometry} position={[width / 2, height / 2, length / 2]} raycast={noRaycast}>
        <lineBasicMaterial ref={outline} color={palette.truckEdge} transparent opacity={0.6} />
      </lineSegments>
    </group>
  )
}
