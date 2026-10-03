import { Edges } from '@react-three/drei'
import { sceneColors } from '../../theme'
import type { Vec3 } from '../../viewer/geometry'

interface PackageBoxProps {
  size: Vec3
  center: Vec3
  isFragile: boolean
  selected: boolean
}

export function PackageBox({ size, center, isFragile, selected }: PackageBoxProps) {
  return (
    <mesh position={center}>
      <boxGeometry args={size} />
      <meshStandardMaterial color={selected ? sceneColors.accent : isFragile ? sceneColors.fragile : sceneColors.package} metalness={0.28} roughness={0.58} />
      <Edges color={sceneColors.canvas} />
    </mesh>
  )
}
