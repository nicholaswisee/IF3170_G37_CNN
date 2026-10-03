import { Edges } from '@react-three/drei'
import { sceneColors } from '../../theme'
import type { Vec3 } from '../../viewer/geometry'

interface ContainerBoxProps {
  size: Vec3
  center: Vec3
}

export function ContainerBox({ size, center }: ContainerBoxProps) {
  return (
    <mesh position={center}>
      <boxGeometry args={size} />
      <meshBasicMaterial color={sceneColors.accent} transparent opacity={0.04} depthWrite={false} />
      <Edges color={sceneColors.accent} />
    </mesh>
  )
}
