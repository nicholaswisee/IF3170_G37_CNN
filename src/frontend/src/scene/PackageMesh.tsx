import { useFrame } from '@react-three/fiber'
import { useRef } from 'react'
import { BoxGeometry, EdgesGeometry, Vector3, type LineBasicMaterial, type Mesh, type MeshStandardMaterial, type Texture } from 'three'
import { palette } from '../theme'
import { arcHeight, type ScenePackage } from '../viewer/sceneModel'
import type { SceneTag } from './sceneTags'

const UNIT_BOX = new BoxGeometry(1, 1, 1)
const UNIT_EDGES = new EdgesGeometry(UNIT_BOX)
// Shrinks each box slightly so neighbors read as separate packages.
const VISUAL_GAP = 0.08
const FLASH_MS = 1700
const noRaycast = () => null

interface Motion {
  from: Vector3
  to: Vector3
  sizeFrom: Vector3
  sizeTo: Vector3
  start: number
  duration: number
  arc: number
  truckId: string | null
}

interface PackageMeshProps {
  item: ScenePackage
  color: string
  stripes: Texture | null
  /** Target opacity; packages outside a locked truck fade back. */
  opacity: number
  transitionMs: number
  tallestTruck: number
  /** Changes identity on each replay step that moved this package, which starts a short highlight. */
  flashToken: object | null
  selected: boolean
}

function easeInOut(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

/*
 * One package as a unit cube scaled to its size. Moves glide between
 * placements; a package that changes trucks or crosses to the Dock follows an
 * arc above the walls so transfers are easy to follow during replay.
 */
export function PackageMesh({ item, color, stripes, opacity, transitionMs, tallestTruck, flashToken, selected }: PackageMeshProps) {
  const mesh = useRef<Mesh>(null)
  const material = useRef<MeshStandardMaterial>(null)
  const edges = useRef<LineBasicMaterial>(null)
  const motion = useRef<Motion | null>(null)
  const flash = useRef<{ token: object | null; start: number }>({ token: null, start: -Infinity })
  const fade = useRef(opacity)

  useFrame((_, delta) => {
    const box = mesh.current
    const surface = material.current
    if (!box || !surface) return
    const now = performance.now()
    const [cx, cy, cz] = item.center
    const sx = item.size[0] - VISUAL_GAP
    const sy = item.size[1] - VISUAL_GAP
    const sz = item.size[2] - VISUAL_GAP

    let current = motion.current
    if (!current) {
      box.position.set(cx, cy, cz)
      box.scale.set(sx, sy, sz)
      current = {
        from: new Vector3(cx, cy, cz), to: new Vector3(cx, cy, cz),
        sizeFrom: new Vector3(sx, sy, sz), sizeTo: new Vector3(sx, sy, sz),
        start: now, duration: 0, arc: 0, truckId: item.truckId,
      }
      motion.current = current
    } else if (current.to.x !== cx || current.to.y !== cy || current.to.z !== cz || current.sizeTo.x !== sx || current.sizeTo.y !== sy || current.sizeTo.z !== sz || current.truckId !== item.truckId) {
      current.from.copy(box.position)
      current.sizeFrom.copy(box.scale)
      current.to.set(cx, cy, cz)
      current.sizeTo.set(sx, sy, sz)
      current.arc = current.truckId !== item.truckId
        ? arcHeight([current.from.x, current.from.y, current.from.z], item.center, tallestTruck)
        : 0
      current.truckId = item.truckId
      current.start = now
      current.duration = transitionMs
    }

    const progress = current.duration <= 0 ? 1 : Math.min(1, (now - current.start) / current.duration)
    const eased = easeInOut(progress)
    box.position.lerpVectors(current.from, current.to, eased)
    if (current.arc > 0) box.position.y += Math.sin(Math.PI * eased) * current.arc
    box.scale.lerpVectors(current.sizeFrom, current.sizeTo, eased)

    fade.current += (opacity - fade.current) * Math.min(1, delta * 9)
    const solid = fade.current > 0.985
    surface.opacity = fade.current
    if (surface.transparent === solid) {
      // Three.js compiles opaque materials with alpha forced to 1, so switching needs a recompile.
      surface.transparent = !solid
      surface.depthWrite = solid
      surface.needsUpdate = true
    }
    box.castShadow = fade.current > 0.5
    if (edges.current) edges.current.opacity = 0.22 * fade.current

    if (flashToken !== null && flashToken !== flash.current.token) flash.current = { token: flashToken, start: now }
    const glow = Math.max(0, 1 - (now - flash.current.start) / FLASH_MS)
    surface.emissiveIntensity = Math.max(glow * 0.5, selected ? 0.28 : 0)
  })

  const tag: SceneTag = { kind: 'package', id: item.id, truckId: item.truckId }
  return (
    <mesh ref={mesh} geometry={UNIT_BOX} userData={tag} castShadow receiveShadow>
      <meshStandardMaterial ref={material} color={color} map={stripes} roughness={0.6} metalness={0} emissive={palette.accent} emissiveIntensity={0} />
      <lineSegments geometry={UNIT_EDGES} raycast={noRaycast}>
        <lineBasicMaterial ref={edges} color={palette.packageEdge} transparent opacity={0.22} />
      </lineSegments>
    </mesh>
  )
}
