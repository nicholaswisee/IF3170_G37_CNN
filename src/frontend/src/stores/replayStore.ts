import { useEffect } from 'react'
import { create } from 'zustand'
import type { ExperimentResult, OptimizationState } from '../types/experiment'

const defaultPlaybackSpeed = 1
const basePlaybackStepMs = 900
// Package motion finishes before the next playback step so blocks settle between iterations.
const transitionShareOfStep = 0.75

/** Speeds offered by the playback bar; long SA runs need the faster ones. */
export const PLAYBACK_SPEEDS = [0.5, 1, 2, 4, 8, 16] as const

/** Delay between automatic replay steps at the given playback speed. */
export function playbackStepMs(speed: number): number {
  return basePlaybackStepMs / speed
}

/** How long a package takes to glide to its next placement at the given playback speed. */
export function packageTransitionSeconds(speed: number): number {
  return (playbackStepMs(speed) * transitionShareOfStep) / 1000
}

/** Which state the viewer shows: the replayed iteration or a stored run state. */
export type StateView = 'replay' | 'initial' | 'final' | 'best'

interface ReplayState {
  experiment: ExperimentResult | null
  currentIteration: number
  stateView: StateView
  isPlaying: boolean
  playbackSpeed: number
  /**
   * Speed of the package motion for the latest change. Only automatic playback steps
   * follow the playback speed; switching views, stepping, and scrubbing move at 1x.
   */
  motionSpeed: number
  setExperiment: (experiment: ExperimentResult) => void
  setStateView: (stateView: StateView) => void
  play: () => void
  pause: () => void
  advancePlayback: () => void
  next: () => void
  previous: () => void
  setIteration: (iteration: number) => void
  setPlaybackSpeed: (speed: number) => void
  reset: () => void
}

export function lastIteration(experiment: ExperimentResult | null): number {
  return Math.max((experiment?.history.length ?? 1) - 1, 0)
}

export function selectReplayState(
  experiment: ExperimentResult | null,
  currentIteration: number,
  stateView: StateView = 'replay',
): OptimizationState | null {
  if (!experiment) return null
  switch (stateView) {
    case 'initial':
      return experiment.initial_state
    case 'final':
      return experiment.final_state
    case 'best':
      return experiment.best_state
    case 'replay':
      return experiment.history[currentIteration]?.state_snapshot ?? experiment.best_state
  }
}

// Stepping or playing the replay always returns the viewer to replay mode; manual steps pause playback.
export const useReplayStore = create<ReplayState>((set) => ({
  experiment: null,
  currentIteration: 0,
  stateView: 'replay',
  isPlaying: false,
  playbackSpeed: defaultPlaybackSpeed,
  motionSpeed: 1,
  setExperiment: (experiment) => set({ experiment, currentIteration: 0, stateView: 'replay', isPlaying: false, motionSpeed: 1 }),
  setStateView: (stateView) => set({ stateView, isPlaying: false, motionSpeed: 1 }),
  // Playing from the last iteration restarts the replay; a single-step history has nothing to play.
  play: () => set((state) => {
    const last = lastIteration(state.experiment)
    const restart = state.currentIteration >= last
    return { isPlaying: last > 0, stateView: 'replay', currentIteration: restart ? 0 : state.currentIteration, motionSpeed: restart ? 1 : state.motionSpeed }
  }),
  pause: () => set({ isPlaying: false }),
  advancePlayback: () => set((state) => {
    if (!state.isPlaying) return {}
    const last = lastIteration(state.experiment)
    const currentIteration = Math.min(state.currentIteration + 1, last)
    return { currentIteration, isPlaying: currentIteration < last, motionSpeed: state.playbackSpeed }
  }),
  next: () => set((state) => ({ currentIteration: Math.min(state.currentIteration + 1, lastIteration(state.experiment)), stateView: 'replay', isPlaying: false, motionSpeed: 1 })),
  previous: () => set((state) => ({ currentIteration: Math.max(state.currentIteration - 1, 0), stateView: 'replay', isPlaying: false, motionSpeed: 1 })),
  setIteration: (iteration) => set((state) => ({ currentIteration: Math.min(Math.max(iteration, 0), lastIteration(state.experiment)), stateView: 'replay', isPlaying: false, motionSpeed: 1 })),
  setPlaybackSpeed: (playbackSpeed) => set({ playbackSpeed }),
  reset: () => set({ experiment: null, currentIteration: 0, stateView: 'replay', isPlaying: false, playbackSpeed: defaultPlaybackSpeed, motionSpeed: 1 }),
}))

/** Advances the replay one iteration per playback step while playing. */
export function usePlaybackTicker(): void {
  const isPlaying = useReplayStore((state) => state.isPlaying)
  const currentIteration = useReplayStore((state) => state.currentIteration)
  const playbackSpeed = useReplayStore((state) => state.playbackSpeed)
  const advancePlayback = useReplayStore((state) => state.advancePlayback)

  useEffect(() => {
    if (!isPlaying) return
    const timer = setTimeout(advancePlayback, playbackStepMs(playbackSpeed))
    return () => clearTimeout(timer)
  }, [isPlaying, currentIteration, playbackSpeed, advancePlayback])
}
