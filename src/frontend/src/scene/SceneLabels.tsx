import { useFrame } from '@react-three/fiber'
import { useRef, type RefObject } from 'react'
import { DoubleSide, MathUtils, NoBlending, Vector2, Vector3, type Mesh, type PerspectiveCamera, type ShaderMaterial } from 'three'
import type { Vec3 } from '../viewer/geometry'
import type { SceneTag } from './sceneTags'

/*
 * Floating labels that obey 3D depth.
 *
 * The labels are ordinary DOM elements placed behind the transparent canvas.
 * For each one the scene holds an invisible, camera facing "hole" with the
 * label's exact screen size and rounded corners. The hole writes depth and a
 * fully transparent color, so the canvas shows the label through it, while
 * anything nearer the camera draws over the hole and covers the label pixel by
 * pixel. Glass walls in front tint the label; objects behind never cover it.
 * Pointer events reach the holes through the normal scene picking.
 *
 * The hole slides toward the camera along the anchor's sight line by the
 * label's reach, so the label reads as standing in front of its own truck or
 * Dock instead of cutting through the boxes inside it. Sliding along the sight
 * line keeps its screen position unchanged.
 */

export interface SceneLabel {
  key: string
  anchor: Vec3
  /** World distance from the anchor to the far edge of what the label names; nothing within it covers the label. */
  reach: number
  tag: SceneTag
  title: string
  detail: string
  /** Capacity used in percent; omitted for labels without a bar. */
  share?: number
  dimmed: boolean
  dock?: boolean
  onSelect: () => void
}

const LABEL_RADIUS_PX = 14

const holeVertexShader = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

// Rounded rectangle in pixel units; outside the corners the hole lets the scene through.
const holeFragmentShader = /* glsl */ `
  uniform vec2 uSize;
  uniform float uRadius;
  varying vec2 vUv;
  void main() {
    vec2 p = (vUv - 0.5) * uSize;
    vec2 q = abs(p) - (uSize * 0.5 - uRadius);
    float distance = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - uRadius;
    if (distance > 0.0) discard;
    gl_FragColor = vec4(0.0);
  }
`

const anchorPoint = new Vector3()
const viewPoint = new Vector3()
const holePoint = new Vector3()
const cameraPoint = new Vector3()

// The camera flight and the damped orbit controls run at -1, so labels and holes
// follow this frame's camera, not the last. Priorities above zero would take over
// rendering, which is why the camera moves earlier instead of the labels later.
const LABEL_FRAME_PRIORITY = 0

/** The depth holes, rendered inside the Canvas. Positions the DOM labels every frame. */
export function LabelHoles({ labels, elements }: { labels: SceneLabel[]; elements: RefObject<Map<string, HTMLElement>> }) {
  const meshes = useRef(new Map<string, Mesh>())

  useFrame(({ camera, size }) => {
    const perspective = camera as PerspectiveCamera
    // The renderer refreshes the view matrix only when it draws, which is after this callback.
    camera.updateMatrixWorld()
    cameraPoint.setFromMatrixPosition(camera.matrixWorld)
    const halfFov = MathUtils.degToRad(perspective.fov) / 2
    for (const label of labels) {
      const element = elements.current.get(label.key)
      const mesh = meshes.current.get(label.key)
      if (!element || !mesh) continue
      anchorPoint.set(label.anchor[0], label.anchor[1], label.anchor[2])
      const depth = -viewPoint.copy(anchorPoint).applyMatrix4(camera.matrixWorldInverse).z
      if (depth <= camera.near) {
        element.style.visibility = 'hidden'
        mesh.visible = false
        continue
      }
      const holeDepth = Math.max(depth - label.reach, camera.near * 2)
      holePoint.copy(anchorPoint).sub(cameraPoint).multiplyScalar(holeDepth / depth).add(cameraPoint)

      anchorPoint.project(camera)
      const x = ((anchorPoint.x + 1) / 2) * size.width
      const y = ((1 - anchorPoint.y) / 2) * size.height
      element.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`
      element.style.visibility = 'visible'

      const width = element.offsetWidth
      const height = element.offsetHeight
      const worldPerPixel = (2 * holeDepth * Math.tan(halfFov)) / size.height
      mesh.visible = true
      mesh.position.copy(holePoint)
      mesh.quaternion.copy(camera.quaternion)
      mesh.scale.set(Math.max(width, 1) * worldPerPixel, Math.max(height, 1) * worldPerPixel, 1)
      const uniforms = (mesh.material as ShaderMaterial).uniforms
      uniforms.uSize.value.set(width, height)
    }
  }, LABEL_FRAME_PRIORITY)

  return (
    <>
      {labels.map((label) => (
        <mesh
          key={label.key}
          ref={(mesh) => {
            if (mesh) meshes.current.set(label.key, mesh)
            else meshes.current.delete(label.key)
          }}
          userData={label.tag}
          visible={false}
        >
          <planeGeometry />
          <shaderMaterial
            args={[{
              uniforms: { uSize: { value: new Vector2(1, 1) }, uRadius: { value: LABEL_RADIUS_PX } },
              vertexShader: holeVertexShader,
              fragmentShader: holeFragmentShader,
            }]}
            blending={NoBlending}
            side={DoubleSide}
          />
        </mesh>
      ))}
    </>
  )
}

/** The DOM labels, rendered behind the canvas. Mouse picks go through the holes; keyboard users can still focus and press them. */
export function LabelLayer({ labels, elements }: { labels: SceneLabel[]; elements: RefObject<Map<string, HTMLElement>> }) {
  return (
    <div className="scene-labels">
      {labels.map((label) => (
        <button
          key={label.key}
          type="button"
          ref={(element) => {
            if (element) elements.current.set(label.key, element)
            else elements.current.delete(label.key)
          }}
          className={`truck-label${label.dimmed ? ' dim' : ''}${label.dock ? ' dock' : ''}`}
          onClick={label.onSelect}
        >
          <b>{label.title}</b>
          <small>{label.detail}</small>
          {label.share !== undefined && (
            <span className="capacity-bar" aria-hidden="true"><i className={label.share > 85 ? 'high' : undefined} style={{ width: `${label.share}%` }} /></span>
          )}
        </button>
      ))}
    </div>
  )
}
