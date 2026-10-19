import { OrbitControls } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useEffectEvent, useImperativeHandle, useRef, type ComponentRef, type Ref } from 'react'
import { MathUtils, Vector3, type PerspectiveCamera } from 'three'
import { prefersReducedMotion } from '../ui/motion'
import type { FleetLayout } from '../viewer/geometry'
import { dockFrame, fleetFrame, truckFrame, type Frame } from '../viewer/sceneModel'
import type { TruckSpec } from '../types/experiment'
import { CAMERA_PRESETS } from './cameraPresets'

export interface CameraCommands {
  fit: () => void
  zoom: (factor: number) => void
  focusDock: () => void
}

interface Flight {
  fromPosition: Vector3
  toPosition: Vector3
  fromTarget: Vector3
  toTarget: Vector3
  start: number
  duration: number
  done?: () => void
}

interface CameraRigProps {
  layout: FleetLayout
  trucks: TruckSpec[]
  lockedTruckId: string | null
  preset: number
  /** Pixels to move the view center so the scene sits between open panels. */
  viewShift: number
  /** Pixels of canvas width hidden behind open panels, used when fitting. */
  coveredWidth: number
  commands: Ref<CameraCommands | null>
}

function easeInOut(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

const toVector = ([x, y, z]: readonly number[]) => new Vector3(x, y, z)

/*
 * Free view orbits and pans across the whole fleet. Locking a truck flies the
 * camera to it and then limits the orbit to that truck: no panning, a zoom
 * range sized to the truck, and the camera stays above the floor.
 */
export function CameraRig({ layout, trucks, lockedTruckId, preset, viewShift, coveredWidth, commands }: CameraRigProps) {
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null)
  const get = useThree((state) => state.get)
  const flight = useRef<Flight | null>(null)
  const shift = useRef(viewShift)
  const appliedView = useRef('')
  const settled = useRef(false)

  const fitDistance = (radius: number) => {
    const { camera, size } = get()
    const halfVertical = MathUtils.degToRad((camera as PerspectiveCamera).fov) / 2
    const visibleAspect = Math.max(0.4, (size.width - coveredWidth) / Math.max(size.height, 1))
    const halfHorizontal = Math.atan(Math.tan(halfVertical) * visibleAspect)
    return radius / Math.sin(Math.min(halfVertical, halfHorizontal))
  }

  const fly = (position: Vector3, target: Vector3, duration: number, done?: () => void) => {
    const orbit = controls.current
    if (!orbit) return
    flight.current = {
      fromPosition: get().camera.position.clone(),
      toPosition: position,
      fromTarget: orbit.target.clone(),
      toTarget: target,
      start: performance.now(),
      duration: prefersReducedMotion() ? 0 : duration,
      done,
    }
    orbit.enabled = false
  }

  const openLimits = () => {
    const orbit = controls.current
    if (!orbit) return
    orbit.enablePan = true
    orbit.minDistance = 0.1
    orbit.maxDistance = 2000
    orbit.maxPolarAngle = Math.PI * 0.49
  }

  const freeLimits = () => {
    const orbit = controls.current
    if (!orbit) return
    orbit.enablePan = true
    orbit.minDistance = 4
    orbit.maxDistance = Math.max(80, fitDistance(fleetFrame(layout).radius) * 3)
    orbit.maxPolarAngle = Math.PI * 0.49
  }

  const lockLimits = (frame: Frame) => {
    const orbit = controls.current
    if (!orbit) return
    orbit.enablePan = false
    orbit.minDistance = frame.radius * 1.25
    orbit.maxDistance = fitDistance(frame.radius) * 2.2
    orbit.maxPolarAngle = Math.PI * 0.47
  }

  const viewFrom = (frame: Frame, distance: number) => toVector(frame.center).addScaledVector(CAMERA_PRESETS[preset].direction, distance)

  const frameFleet = (duration: number) => {
    const frame = fleetFrame(layout)
    openLimits()
    fly(viewFrom(frame, fitDistance(frame.radius) * 0.92), toVector(frame.center), duration, freeLimits)
  }

  const frameTruck = (truck: TruckSpec, duration: number) => {
    const frame = truckFrame(layout, truck)
    openLimits()
    fly(viewFrom(frame, fitDistance(frame.radius) * 1.35), toVector(frame.center), duration, () => lockLimits(frame))
  }

  const frameSelection = (duration: number) => {
    const truck = trucks.find((candidate) => candidate.id === lockedTruckId)
    if (truck) frameTruck(truck, duration)
    else frameFleet(duration)
  }

  // The first framing snaps into place; later lock, preset, and fleet changes fly.
  const reframe = useEffectEvent(() => {
    frameSelection(settled.current ? 800 : 0)
    settled.current = true
  })

  const layoutKey = `${trucks.map((truck) => `${truck.id}:${truck.width}x${truck.length}x${truck.height}`).join('|')}|${layout.dock.columns}x${layout.dock.rows}`
  useEffect(() => {
    reframe()
  }, [lockedTruckId, preset, layoutKey])

  useImperativeHandle(commands, () => ({
    fit: () => frameSelection(800),
    zoom: (factor: number) => {
      const orbit = controls.current
      if (!orbit) return
      const { camera } = get()
      const offset = camera.position.clone().sub(orbit.target)
      const distance = MathUtils.clamp(offset.length() * factor, orbit.minDistance, orbit.maxDistance)
      fly(orbit.target.clone().add(offset.setLength(distance)), orbit.target.clone(), 280)
    },
    focusDock: () => {
      const frame = dockFrame(layout)
      openLimits()
      fly(toVector(frame.center).addScaledVector(new Vector3(0.3, 0.9, 0.8).normalize(), fitDistance(frame.radius) * 1.1), toVector(frame.center), 800, freeLimits)
    },
  }))

  useFrame((state, delta) => {
    const camera = state.camera as PerspectiveCamera
    const gap = viewShift - shift.current
    shift.current = Math.abs(gap) < 0.5 ? viewShift : shift.current + gap * Math.min(1, delta * 7)
    const { width, height } = state.size
    const viewKey = `${width}x${height}:${shift.current.toFixed(1)}`
    if (viewKey !== appliedView.current) {
      camera.setViewOffset(width, height, -shift.current, 0, width, height)
      camera.updateProjectionMatrix()
      appliedView.current = viewKey
    }

    const orbit = controls.current
    const current = flight.current
    if (!orbit || !current) return
    const progress = current.duration <= 0 ? 1 : Math.min(1, (performance.now() - current.start) / current.duration)
    const eased = easeInOut(progress)
    camera.position.lerpVectors(current.fromPosition, current.toPosition, eased)
    orbit.target.lerpVectors(current.fromTarget, current.toTarget, eased)
    camera.lookAt(orbit.target)
    if (progress >= 1) {
      flight.current = null
      orbit.enabled = true
      current.done?.()
      orbit.update()
    }
    // Same priority as the drei controls update, ahead of the labels at 0 (see SceneLabels.tsx).
  }, -1)

  return <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={0.08} screenSpacePanning={false} />
}
