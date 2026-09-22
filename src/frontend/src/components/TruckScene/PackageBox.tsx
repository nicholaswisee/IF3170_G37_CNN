import { sceneColors } from '../../theme'

interface PackageBoxProps {
  id: string
  position: [number, number, number]
  dimensions: [number, number, number]
  isFragile: boolean
  selected: boolean
  onSelect: (id: string) => void
}

export function PackageBox({ id, position, dimensions, isFragile, selected, onSelect }: PackageBoxProps) {
  return (
    <mesh position={position} onClick={() => onSelect(id)}>
      <boxGeometry args={dimensions} />
      <meshStandardMaterial color={selected ? sceneColors.accent : isFragile ? sceneColors.fragile : sceneColors.package} metalness={0.28} roughness={0.58} />
    </mesh>
  )
}
