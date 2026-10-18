import assert from 'node:assert/strict'
import test from 'node:test'
import { packageTransitionSeconds, playbackStepMs, selectReplayState, useReplayStore } from './replayStore'
import type { ExperimentResult, OptimizationState } from '../types/experiment'

const best: OptimizationState = { placements: [] }
const first: OptimizationState = { placements: [{ package_id: 'a', truck_id: null, position: null, orientation: 0 }] }
const second: OptimizationState = { placements: [{ package_id: 'b', truck_id: null, position: null, orientation: 0 }] }
const experiment = {
  best_state: best,
  history: [{ state_snapshot: first }, { state_snapshot: second }],
} as ExperimentResult
const withoutSnapshot = {
  ...experiment,
  history: [{ ...experiment.history[0], state_snapshot: null }],
} as ExperimentResult

test('selects the current iteration snapshot and falls back to best state', () => {
  assert.equal(selectReplayState(experiment, 0), first)
  assert.equal(selectReplayState(experiment, 1), second)
  assert.equal(selectReplayState(withoutSnapshot, 0), best)
})

test('falls back to best state for empty history and to null without an experiment', () => {
  assert.equal(selectReplayState({ ...experiment, history: [] }, 0), best)
  assert.equal(selectReplayState(null, 0), null)
})

test('initial, final, and best views select the stored run states', () => {
  const initial: OptimizationState = { placements: [] }
  const final: OptimizationState = { placements: [] }
  const run = { ...experiment, initial_state: initial, final_state: final } as ExperimentResult
  assert.equal(selectReplayState(run, 1, 'initial'), initial)
  assert.equal(selectReplayState(run, 1, 'final'), final)
  assert.equal(selectReplayState(run, 1, 'best'), best)
  assert.equal(selectReplayState(run, 1, 'replay'), second)
  assert.equal(selectReplayState({ ...run, best_state: final }, 0, 'best'), selectReplayState({ ...run, best_state: final }, 0, 'final'))
  assert.equal(selectReplayState(null, 0, 'best'), null)
})

test('choosing a stored view keeps the iteration, and stepping returns to replay', () => {
  const store = useReplayStore.getState()
  store.reset()
  store.setExperiment(experiment)
  store.next()
  store.setStateView('initial')
  assert.equal(useReplayStore.getState().stateView, 'initial')
  assert.equal(useReplayStore.getState().currentIteration, 1)
  store.previous()
  assert.equal(useReplayStore.getState().stateView, 'replay')
  store.setStateView('best')
  store.setExperiment(experiment)
  assert.equal(useReplayStore.getState().stateView, 'replay')
  store.setStateView('final')
  store.reset()
  assert.equal(useReplayStore.getState().stateView, 'replay')
})

test('replay navigation and explicit selection stay within the available history', () => {
  const store = useReplayStore.getState()
  store.reset()
  store.setExperiment(experiment)
  store.previous()
  assert.equal(useReplayStore.getState().currentIteration, 0)
  store.next()
  assert.equal(useReplayStore.getState().currentIteration, 1)
  store.next()
  assert.equal(useReplayStore.getState().currentIteration, 1)
  store.setIteration(20)
  assert.equal(useReplayStore.getState().currentIteration, 1)
  store.setIteration(-2)
  assert.equal(useReplayStore.getState().currentIteration, 0)
  store.reset()
})

test('playback advances one iteration per step and pauses on the last iteration', () => {
  const store = useReplayStore.getState()
  store.reset()
  store.setExperiment(experiment)
  store.advancePlayback()
  assert.equal(useReplayStore.getState().currentIteration, 0, 'advancing while paused is a no-op')
  store.play()
  assert.equal(useReplayStore.getState().isPlaying, true)
  store.advancePlayback()
  assert.equal(useReplayStore.getState().currentIteration, 1)
  assert.equal(useReplayStore.getState().isPlaying, false)
  store.reset()
})

test('playing from the last iteration restarts and manual steps pause playback', () => {
  const store = useReplayStore.getState()
  store.reset()
  store.setExperiment(experiment)
  store.setIteration(1)
  store.play()
  assert.equal(useReplayStore.getState().currentIteration, 0)
  assert.equal(useReplayStore.getState().isPlaying, true)
  store.next()
  assert.equal(useReplayStore.getState().isPlaying, false)
  store.play()
  store.previous()
  assert.equal(useReplayStore.getState().isPlaying, false)
  store.reset()
})

test('play does nothing without a replayable history', () => {
  const store = useReplayStore.getState()
  store.reset()
  store.play()
  assert.equal(useReplayStore.getState().isPlaying, false)
  store.setExperiment(withoutSnapshot)
  store.play()
  assert.equal(useReplayStore.getState().isPlaying, false)
  store.reset()
})

test('faster playback shortens both the step delay and the package transition', () => {
  assert.equal(playbackStepMs(2), playbackStepMs(1) / 2)
  assert.ok(packageTransitionSeconds(1) * 1000 < playbackStepMs(1), 'packages settle before the next step')
  assert.equal(packageTransitionSeconds(2), packageTransitionSeconds(1) / 2)
})

test('only automatic playback steps move packages at the playback speed', () => {
  const store = useReplayStore.getState()
  store.reset()
  store.setExperiment({ ...experiment, history: [...experiment.history, { state_snapshot: first }] } as ExperimentResult)
  store.setPlaybackSpeed(8)
  store.play()
  store.advancePlayback()
  assert.equal(useReplayStore.getState().motionSpeed, 8)
  for (const view of ['initial', 'final', 'best', 'replay'] as const) {
    store.setStateView(view)
    assert.equal(useReplayStore.getState().motionSpeed, 1, view)
  }
  store.play()
  store.advancePlayback()
  assert.equal(useReplayStore.getState().motionSpeed, 8)
  store.previous()
  assert.equal(useReplayStore.getState().motionSpeed, 1)
  store.reset()
})
