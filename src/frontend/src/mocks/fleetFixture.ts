import type { OptimizationState, Orientation, PackagePlacement, Problem } from '../types/experiment'

/*
 * Frozen-schema fleet used by the viewer until the backend returns real
 * experiments. Every state here passes the backend validate_state. It covers
 * stacking, fragile packages on top, partial support, a rotated package,
 * trucks of different sizes, an empty truck, and outside packages.
 */

export const mockProblem: Problem = {
  trucks: [
    { id: 'truck-a', width: 10, length: 8, height: 6, max_capacity: 100 },
    { id: 'truck-b', width: 6, length: 5, height: 4, max_capacity: 50 },
    { id: 'truck-c', width: 4, length: 4, height: 3, max_capacity: 20 },
  ],
  packages: [
    { id: 'P01', width: 4, length: 3, height: 2, value: 40, weight: 20, is_fragile: false, eta: 2 },
    { id: 'P02', width: 3, length: 3, height: 2, value: 30, weight: 15, is_fragile: false, eta: 1 },
    { id: 'P03', width: 2, length: 2, height: 1, value: 25, weight: 5, is_fragile: true, eta: 0 },
    { id: 'P04', width: 2, length: 4, height: 3, value: 35, weight: 18, is_fragile: false, eta: 3 },
    { id: 'P05', width: 3, length: 2, height: 2, value: 20, weight: 10, is_fragile: false, eta: 4 },
    { id: 'P06', width: 1, length: 1, height: 1, value: 8, weight: 2, is_fragile: true, eta: 1 },
    { id: 'P07', width: 5, length: 4, height: 3, value: 50, weight: 30, is_fragile: false, eta: 2 },
    { id: 'P08', width: 6, length: 6, height: 6, value: 60, weight: 40, is_fragile: false, eta: 5 },
    { id: 'P09', width: 2, length: 2, height: 2, value: 12, weight: 6, is_fragile: false, eta: 0 },
  ],
}

function at(packageId: string, truckId: string, x: number, y: number, z: number, orientation: Orientation = 0): PackagePlacement {
  return { package_id: packageId, truck_id: truckId, position: { x, y, z }, orientation }
}

function outside(packageId: string): PackagePlacement {
  return { package_id: packageId, truck_id: null, position: null, orientation: 0 }
}

const initial: OptimizationState = {
  placements: [
    at('P01', 'truck-a', 0, 0, 0),
    outside('P02'),
    at('P03', 'truck-a', 6, 5, 0),
    outside('P04'),
    outside('P05'),
    outside('P06'),
    at('P07', 'truck-b', 0, 0, 0),
    outside('P08'),
    outside('P09'),
  ],
}

const best: OptimizationState = {
  placements: [
    at('P01', 'truck-a', 0, 0, 0),
    at('P02', 'truck-a', 4, 0, 0),
    // Fragile on top of P01: allowed because nothing rests on it.
    at('P03', 'truck-a', 0, 0, 2),
    // HLW turns 2x4x3 into an effective 3x4x2 footprint.
    at('P04', 'truck-a', 0, 3, 0, 5),
    at('P05', 'truck-a', 4, 0, 2),
    at('P06', 'truck-b', 0, 0, 3),
    at('P07', 'truck-b', 0, 0, 0),
    // Exceeds truck-a's remaining capacity, so it stays outside.
    outside('P08'),
    // Only half of its base rests on P04: partial support is valid.
    at('P09', 'truck-a', 2, 3, 2),
  ],
}

export const mockStates: Record<'initial' | 'final' | 'best', OptimizationState> = {
  initial,
  final: best,
  best,
}
