import { Grid, OrbitControls, PerspectiveCamera } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { useMemo } from 'react'
import { sceneColors } from '../../theme'
import type { OptimizationState, Problem } from '../../types/experiment'
import { toThreeCenter, toThreeSize, truckToThree, type Vec3 } from '../../viewer/geometry'
import { normalizeViewerState } from '../../viewer/normalize'
import { ContainerBox } from './ContainerBox'
import { PackageBox } from './PackageBox'

interface TruckSceneProps {
  problem: Problem
  state: OptimizationState
  truckId: string
}

export function TruckScene({ problem, state, truckId }: TruckSceneProps) {
  const viewerState = useMemo(() => normalizeViewerState(problem, state), [problem, state])
  const truckSpec = problem.trucks.find((truck) => truck.id === truckId)
  const truck = viewerState.trucks.find((candidate) => candidate.id === truckId)

  if (!truckSpec || !truck) {
    return (
      <div className="truck-scene truck-scene--empty" aria-label="3D truck container preview">
        <p className="scene-caption">Unknown truck: {truckId}</p>
      </div>
    )
  }

  const container = truckToThree(truckSpec)
  const span = Math.max(...container.size)
  const [cx, cy, cz] = container.center
  const cameraPosition: Vec3 = [cx + span * 1.4, cy + span * 1.1, cz + span * 1.7]
  const [width, length, height] = truck.dimensions

  return (
    <div className="truck-scene" aria-label="3D truck container preview">
      <Canvas>
        <PerspectiveCamera makeDefault position={cameraPosition} fov={42} near={0.1} far={span * 20} />
        <color attach="background" args={[sceneColors.canvas]} />
        <ambientLight intensity={0.65} />
        <directionalLight position={[cx + span, cy + span * 1.5, cz + span]} intensity={2.1} />
        <directionalLight position={[cx - span, cy + span * 0.5, cz - span]} intensity={0.55} color={sceneColors.cool} />
        <ContainerBox size={container.size} center={container.center} />
        {truck.packages.map((pkg) => pkg.position && (
          <PackageBox
            key={pkg.id}
            size={toThreeSize(pkg.effectiveDimensions)}
            center={toThreeCenter(pkg.position, pkg.effectiveDimensions)}
            isFragile={pkg.isFragile}
            selected={false}
          />
        ))}
        {/* One grid cell equals one backend unit; the truck's back-left corner sits on the origin. */}
        <Grid infiniteGrid cellSize={1} sectionSize={5} cellColor={sceneColors.grid} sectionColor={sceneColors.gridMajor} fadeDistance={span * 4} position={[0, -0.001, 0]} />
        <OrbitControls makeDefault target={container.center} minDistance={span * 0.5} maxDistance={span * 4} />
      </Canvas>
      <ul className="scene-legend" aria-label="Package colors">
        <li><span style={{ background: sceneColors.package }} aria-hidden="true" />Package</li>
        <li><span style={{ background: sceneColors.fragile }} aria-hidden="true" />Fragile</li>
      </ul>
      <p className="scene-caption">
        {truck.id} / {width}×{length}×{height} / {truck.packages.length} loaded / orbit to inspect
      </p>
    </div>
  )
}
