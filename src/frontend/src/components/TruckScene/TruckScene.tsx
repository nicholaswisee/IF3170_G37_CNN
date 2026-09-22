import { Grid, OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { useState } from 'react'
import { sceneColors } from '../../theme'
import { ContainerBox } from './ContainerBox'
import { PackageBox } from './PackageBox'

const dummyPackages = [
  { id: 'PKG-01', position: [-6, 1, -2] as [number, number, number], dimensions: [3, 2, 3] as [number, number, number], isFragile: false },
  { id: 'PKG-02', position: [-2.2, 1.25, -2] as [number, number, number], dimensions: [3.2, 2.5, 3] as [number, number, number], isFragile: true },
  { id: 'PKG-03', position: [2, 0.75, -2] as [number, number, number], dimensions: [2.6, 1.5, 3] as [number, number, number], isFragile: false },
  { id: 'PKG-04', position: [5.6, 1, 1.8] as [number, number, number], dimensions: [2.8, 2, 3.2] as [number, number, number], isFragile: false },
  { id: 'PKG-05', position: [-1.5, 1.1, 2] as [number, number, number], dimensions: [3.6, 2.2, 2.5] as [number, number, number], isFragile: true },
]

export function TruckScene() {
  const [selectedPackage, setSelectedPackage] = useState(dummyPackages[0].id)

  return (
    <div className="truck-scene" aria-label="Interactive 3D truck container preview">
      <Canvas camera={{ position: [17, 13, 18], fov: 42 }}>
        <color attach="background" args={[sceneColors.canvas]} />
        <ambientLight intensity={0.65} />
        <directionalLight position={[10, 13, 8]} intensity={2.1} />
        <directionalLight position={[-10, 5, -8]} intensity={0.55} color={sceneColors.cool} />
        <ContainerBox dimensions={[20, 5, 10]} />
        {dummyPackages.map((packageItem) => (
          <PackageBox
            key={packageItem.id}
            {...packageItem}
            selected={packageItem.id === selectedPackage}
            onSelect={setSelectedPackage}
          />
        ))}
        <Grid args={[40, 40]} cellColor={sceneColors.grid} sectionColor={sceneColors.gridMajor} fadeDistance={28} position={[0, 0, 0]} />
        <OrbitControls makeDefault minDistance={12} maxDistance={34} target={[0, 2, 0]} />
      </Canvas>
      <p className="scene-caption">Cargo bay / select a package to inspect</p>
    </div>
  )
}
