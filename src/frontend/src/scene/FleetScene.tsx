import { Grid } from '@react-three/drei'
import { Canvas, type ThreeEvent } from '@react-three/fiber'
import { useCallback, useEffect, useMemo, useRef, type Ref, type RefObject } from 'react'
import { CanvasTexture, Object3D, RepeatWrapping } from 'three'
import { formatNumber, formatWhole } from '../copy/format'
import { palette } from '../theme'
import type { OptimizationState, Problem } from '../types/experiment'
import { HoverTip, type HoverTipHandle } from '../shell/HoverTip'
import { prefersReducedMotion } from '../ui/motion'
import { layoutFleet, packageToThree, type FleetLayout, type Vec3 } from '../viewer/geometry'
import { arcHeight, buildScenePackages, changedPackageIds, outsidePackages, packageColor, truckLoads, type ColorMode } from '../viewer/sceneModel'
import { CameraRig, type CameraCommands } from './CameraRig'
import { DockArea } from './DockArea'
import { MoveTrail } from './MoveTrail'
import { PackageMesh } from './PackageMesh'
import { LabelHoles, LabelLayer, type SceneLabel } from './SceneLabels'
import { resolveClick, resolveHoverPackage } from './sceneTags'
import { TruckShell } from './TruckShell'

const MAX_TRAILS = 3
const DIMMED_OPACITY = 0.13

export interface FleetSceneProps {
  problem: Problem
  state: OptimizationState
  /** State shown one replay step earlier; drives move highlights and trails. */
  previousState: OptimizationState | null
  lockedTruckId: string | null
  selectedPackageId: string | null
  colorMode: ColorMode
  showLabels: boolean
  showGrid: boolean
  showTrail: boolean
  transitionSeconds: number
  cameraPreset: number
  viewShift: number
  coveredWidth: number
  cameraCommands: Ref<CameraCommands | null>
  onSelectTruck: (truckId: string) => void
  onSelectPackage: (packageId: string) => void
  onFocusDock: () => void
}

function createStripeTexture(): CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 64
  const context = canvas.getContext('2d')
  if (context) {
    context.fillStyle = '#ffffff'
    context.fillRect(0, 0, 64, 64)
    context.strokeStyle = '#d7d7d7'
    context.lineWidth = 9
    for (let offset = -64; offset < 128; offset += 22) {
      context.beginPath()
      context.moveTo(offset, 0)
      context.lineTo(offset + 64, 64)
      context.stroke()
    }
  }
  const texture = new CanvasTexture(canvas)
  texture.wrapS = texture.wrapT = RepeatWrapping
  return texture
}

interface ContentsProps extends FleetSceneProps {
  layout: FleetLayout
  labels: SceneLabel[]
  labelElements: RefObject<Map<string, HTMLElement>>
  hoverTip: RefObject<HoverTipHandle | null>
  setCursor: (cursor: string) => void
}

function FleetContents({
  problem, state, previousState, lockedTruckId, selectedPackageId, colorMode, showGrid, showTrail,
  transitionSeconds, cameraPreset, viewShift, coveredWidth, cameraCommands, onSelectTruck, onSelectPackage, onFocusDock,
  layout, labels, labelElements, hoverTip, setCursor,
}: ContentsProps) {
  const items = useMemo(() => buildScenePackages(problem, state, layout), [problem, state, layout])
  // A new Set per step doubles as the token that restarts the move highlight.
  const changed = useMemo(() => new Set(changedPackageIds(previousState, state)), [previousState, state])
  const stripes = useMemo(() => createStripeTexture(), [])
  useEffect(() => () => stripes.dispose(), [stripes])
  const lightTarget = useMemo(() => new Object3D(), [])

  const trails = useMemo(() => {
    if (!showTrail || !previousState) return []
    const before = new Map(previousState.placements.map((placement) => [placement.package_id, placement]))
    return items.filter((item) => changed.has(item.id)).slice(0, MAX_TRAILS).flatMap((item) => {
      const old = before.get(item.id)
      if (!old) return []
      const oldTruck = old.truck_id !== null && old.position !== null && layout.offsets[old.truck_id] !== undefined ? old.truck_id : null
      const from: Vec3 = packageToThree(layout, item.spec, item.index, oldTruck, oldTruck ? old.position : null, old.orientation).center
      const crossing = oldTruck !== item.truckId
      const distance = Math.hypot(item.center[0] - from[0], item.center[1] - from[1], item.center[2] - from[2])
      if (distance < 0.01) return []
      return [{ id: item.id, from, to: item.center, arc: crossing ? arcHeight(from, item.center, layout.maxHeight) : 0 }]
    })
  }, [showTrail, previousState, items, changed, layout])

  const transitionMs = prefersReducedMotion() ? 0 : transitionSeconds * 1000
  const center = layout.width / 2
  const shadowReach = Math.max(40, layout.width, layout.dock.originZ + layout.dock.depth)
  const specs = useMemo(() => new Map(problem.packages.map((pkg) => [pkg.id, pkg])), [problem])

  const handlePointerMove = (event: ThreeEvent<PointerEvent>) => {
    event.stopPropagation()
    const target = resolveClick(event.intersections, lockedTruckId)
    setCursor(target ? 'pointer' : 'grab')
    const packageId = resolveHoverPackage(event.intersections, lockedTruckId)
    const spec = packageId ? specs.get(packageId) : undefined
    const { clientX, clientY } = event.nativeEvent
    if (spec) {
      hoverTip.current?.show(`${spec.id}, value ${formatNumber(spec.value)}, ${formatNumber(spec.weight)} kg${spec.is_fragile ? ', fragile' : ''}`, clientX, clientY)
    } else if (target?.kind === 'truck') {
      hoverTip.current?.show(`Click to focus ${target.id}`, clientX, clientY)
    } else {
      hoverTip.current?.hide()
    }
  }

  const handleClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation()
    if (event.delta > 5) return
    const target = resolveClick(event.intersections, lockedTruckId)
    if (!target) return
    if (target.kind === 'truck') onSelectTruck(target.id)
    else if (target.kind === 'package') onSelectPackage(target.id)
    else onFocusDock()
  }

  return (
    <>
      {/* Physically based light units: these values keep the white floors near white. */}
      <hemisphereLight args={['#ffffff', '#e4e9f0', 2.2]} />
      <primitive object={lightTarget} position={[center, 0, layout.maxLength]} />
      <directionalLight
        castShadow
        target={lightTarget}
        position={[center - 25, 55, -18]}
        intensity={1.7}
        shadow-mapSize={[2048, 2048]}
        shadow-radius={6}
        shadow-camera-left={-shadowReach}
        shadow-camera-right={shadowReach}
        shadow-camera-top={shadowReach}
        shadow-camera-bottom={-shadowReach}
        shadow-camera-near={1}
        shadow-camera-far={260}
      />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[center, -0.3, layout.maxLength]} receiveShadow>
        <planeGeometry args={[800, 800]} />
        <shadowMaterial opacity={0.09} />
      </mesh>
      {showGrid && (
        <Grid
          position={[Math.round(center), -0.295, Math.round(layout.maxLength)]}
          infiniteGrid
          cellSize={1}
          sectionSize={5}
          cellColor={palette.gridCell}
          sectionColor={palette.gridSection}
          cellThickness={0.6}
          sectionThickness={1}
          fadeDistance={Math.max(120, shadowReach * 3)}
          fadeStrength={1.4}
        />
      )}
      <group
        onPointerMove={handlePointerMove}
        onPointerOut={() => {
          hoverTip.current?.hide()
          setCursor('grab')
        }}
        onClick={handleClick}
      >
        {problem.trucks.map((truck) => (
          <TruckShell key={truck.id} truck={truck} offset={layout.offsets[truck.id] ?? 0} dimmed={lockedTruckId !== null && lockedTruckId !== truck.id} />
        ))}
        <DockArea dock={layout.dock} />
        <LabelHoles labels={labels} elements={labelElements} />
        {items.map((item) => (
          <PackageMesh
            key={item.id}
            item={item}
            color={packageColor(problem, item.index, colorMode)}
            stripes={item.spec.is_fragile ? stripes : null}
            opacity={lockedTruckId === null || item.truckId === lockedTruckId ? 1 : DIMMED_OPACITY}
            transitionMs={transitionMs}
            tallestTruck={layout.maxHeight}
            flashToken={changed.has(item.id) ? changed : null}
            selected={item.id === selectedPackageId}
          />
        ))}
      </group>
      {trails.map((trail) => <MoveTrail key={trail.id} from={trail.from} to={trail.to} arc={trail.arc} />)}
      <CameraRig
        layout={layout}
        trucks={problem.trucks}
        lockedTruckId={lockedTruckId}
        preset={cameraPreset}
        viewShift={viewShift}
        coveredWidth={coveredWidth}
        commands={cameraCommands}
      />
    </>
  )
}

/** Full-bleed 3D stage showing every truck and the Dock in one scene. */
export function FleetScene(props: FleetSceneProps) {
  const { problem, state, lockedTruckId, showLabels, onSelectTruck, onFocusDock } = props
  const stage = useRef<HTMLDivElement>(null)
  const hoverTip = useRef<HoverTipHandle>(null)
  const labelElements = useRef(new Map<string, HTMLElement>())
  const setCursor = useCallback((cursor: string) => {
    if (stage.current) stage.current.style.cursor = cursor
  }, [])
  const layout = useMemo(() => layoutFleet(problem), [problem])

  const labels = useMemo<SceneLabel[]>(() => {
    if (!showLabels) return []
    const loads = truckLoads(problem, state)
    // The lock bar already names the locked truck, so its own label would only cover it.
    const truckLabels = problem.trucks.filter((truck) => truck.id !== lockedTruckId).map((truck): SceneLabel => {
      const load = loads[truck.id] ?? { weight: 0, count: 0, value: 0 }
      const offset = layout.offsets[truck.id] ?? 0
      return {
        key: `truck:${truck.id}`,
        anchor: [offset + truck.width / 2, truck.height + 1.4, truck.length / 2],
        tag: { kind: 'truck', id: truck.id },
        title: truck.id,
        detail: `${formatWhole(load.weight)} of ${formatWhole(truck.max_capacity)} kg, ${load.count} loaded`,
        share: truck.max_capacity > 0 ? Math.min(100, (load.weight / truck.max_capacity) * 100) : 0,
        dimmed: lockedTruckId !== null,
        onSelect: () => onSelectTruck(truck.id),
      }
    })
    const { dock } = layout
    return [...truckLabels, {
      key: 'dock',
      anchor: [dock.originX + dock.width / 2, 0.6, dock.originZ + dock.depth + 1.6],
      tag: { kind: 'dock' },
      title: 'Dock',
      detail: `${outsidePackages(problem, state).length} outside the fleet`,
      dimmed: lockedTruckId !== null,
      dock: true,
      onSelect: onFocusDock,
    }]
  }, [showLabels, problem, state, lockedTruckId, layout, onSelectTruck, onFocusDock])

  return (
    <>
      <div ref={stage} className="stage" aria-label="3D view of the fleet and the Dock">
        <LabelLayer labels={labels} elements={labelElements} />
        <Canvas shadows flat dpr={[1, 2]} camera={{ fov: 38, near: 0.1, far: 1500, position: [30, 40, 70] }} gl={{ antialias: true, alpha: true }}>
          <FleetContents {...props} layout={layout} labels={labels} labelElements={labelElements} hoverTip={hoverTip} setCursor={setCursor} />
        </Canvas>
      </div>
      <HoverTip ref={hoverTip} />
    </>
  )
}
