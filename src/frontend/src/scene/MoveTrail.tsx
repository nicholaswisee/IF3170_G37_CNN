import { Line } from '@react-three/drei'
import { useMemo } from 'react'
import { palette } from '../theme'
import type { Vec3 } from '../viewer/geometry'
import { arcPoint } from '../viewer/sceneModel'

const SEGMENTS = 48

/** Dashed path showing where a package travelled in the current replay step. */
export function MoveTrail({ from, to, arc }: { from: Vec3; to: Vec3; arc: number }) {
  const points = useMemo(() => Array.from({ length: SEGMENTS + 1 }, (_, index) => arcPoint(from, to, arc, index / SEGMENTS)), [from, to, arc])
  return <Line points={points} color={palette.accent} dashed dashSize={0.45} gapSize={0.3} lineWidth={2} transparent opacity={0.9} />
}
