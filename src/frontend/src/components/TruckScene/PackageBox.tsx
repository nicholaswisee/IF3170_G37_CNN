import { sceneColors } from '../../theme'

interface PackageBoxProps {
  id: string
  position: [number, number, number]
  dimensions: [number, number, number]
  isFragile: boolean
  selected: boolean
}

export function PackageBox({ position, dimensions, isFragile, selected }: PackageBoxProps) {
  return (
    <mesh position={position}>
      <boxGeometry args={dimensions} />
      <meshStandardMaterial color={selected ? sceneColors.accent : isFragile ? sceneColors.fragile : sceneColors.package} metalness={0.28} roughness={0.58} />
    </mesh>
  )
}
