import { sceneColors } from '../../theme'

interface ContainerBoxProps {
  dimensions: [number, number, number]
}

export function ContainerBox({ dimensions }: ContainerBoxProps) {
  return (
    <mesh position={[0, dimensions[1] / 2, 0]}>
      <boxGeometry args={dimensions} />
      <meshStandardMaterial color={sceneColors.accent} transparent opacity={0.34} wireframe />
    </mesh>
  )
}
