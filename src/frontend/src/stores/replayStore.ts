import { create } from 'zustand'
import type { ExperimentResult } from '../types/experiment'

const defaultPlaybackSpeed = 1

interface ReplayState {
  experiment: ExperimentResult | null
  currentIteration: number
  isPlaying: boolean
  playbackSpeed: number
  setExperiment: (experiment: ExperimentResult) => void
  play: () => void
  pause: () => void
  next: () => void
  previous: () => void
  setIteration: (iteration: number) => void
  setPlaybackSpeed: (speed: number) => void
  reset: () => void
}

function lastIteration(experiment: ExperimentResult | null): number {
  return Math.max((experiment?.history.length ?? 1) - 1, 0)
}

export const useReplayStore = create<ReplayState>((set) => ({
  experiment: null,
  currentIteration: 0,
  isPlaying: false,
  playbackSpeed: defaultPlaybackSpeed,
  setExperiment: (experiment) => set({ experiment, currentIteration: 0, isPlaying: false }),
  play: () => set({ isPlaying: true }),
  pause: () => set({ isPlaying: false }),
  next: () => set((state) => ({ currentIteration: Math.min(state.currentIteration + 1, lastIteration(state.experiment)) })),
  previous: () => set((state) => ({ currentIteration: Math.max(state.currentIteration - 1, 0) })),
  setIteration: (iteration) => set((state) => ({ currentIteration: Math.min(Math.max(iteration, 0), lastIteration(state.experiment)) })),
  setPlaybackSpeed: (playbackSpeed) => set({ playbackSpeed }),
  reset: () => set({ experiment: null, currentIteration: 0, isPlaying: false, playbackSpeed: defaultPlaybackSpeed }),
}))
