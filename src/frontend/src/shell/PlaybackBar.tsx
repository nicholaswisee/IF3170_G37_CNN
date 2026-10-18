import type { CSSProperties } from 'react'
import { progressLabel } from '../charts/chartData'
import { formatNumber } from '../copy/format'
import { PLAYBACK_SPEEDS, lastIteration, useReplayStore, type StateView } from '../stores/replayStore'
import type { SearchEvent } from '../types/experiment'
import { Icon } from '../ui/Icon'
import { Segmented } from '../ui/Segmented'

const VIEW_OPTIONS: { value: StateView; label: string }[] = [
  { value: 'replay', label: 'Replay' },
  { value: 'initial', label: 'Initial' },
  { value: 'final', label: 'Final' },
  { value: 'best', label: 'Best' },
]

const VIEW_NAMES: Record<Exclude<StateView, 'replay'>, string> = { initial: 'Initial state', final: 'Final state', best: 'Best state' }

/** Replay transport: step, play, scrub, change speed, and switch between replay and stored states. */
export function PlaybackBar({ shownEvent }: { shownEvent: SearchEvent | null }) {
  const experiment = useReplayStore((state) => state.experiment)
  const currentIteration = useReplayStore((state) => state.currentIteration)
  const stateView = useReplayStore((state) => state.stateView)
  const isPlaying = useReplayStore((state) => state.isPlaying)
  const speed = useReplayStore((state) => state.playbackSpeed)
  const { play, pause, next, previous, setIteration, setPlaybackSpeed, setStateView } = useReplayStore.getState()

  const last = lastIteration(experiment)
  const unit = progressLabel(experiment?.algorithm)
  const idle = !experiment
  const replayable = !!experiment && experiment.history.length > 1
  const percent = last > 0 ? (currentIteration / last) * 100 : 0
  const lastShown = experiment?.history[last]?.iteration ?? last

  let label = 'Preview of the configured problem'
  if (experiment && stateView === 'replay') label = `${unit} ${experiment.history[currentIteration]?.iteration ?? currentIteration} of ${lastShown}`
  else if (experiment && stateView !== 'replay') label = VIEW_NAMES[stateView]

  return (
    <div className="center-lane lane-bottom">
      <div className={idle ? 'playback glass idle' : 'playback glass'}>
        <button className="icon-btn interactive" type="button" aria-label="Previous step" disabled={!replayable} onClick={previous}><Icon name="stepBack" /></button>
        <button className="icon-btn play-main" type="button" aria-label={isPlaying ? 'Pause' : 'Play'} disabled={!replayable} onClick={isPlaying ? pause : play}>
          <Icon name={isPlaying ? 'pause' : 'play'} size={22} />
        </button>
        <button className="icon-btn interactive" type="button" aria-label="Next step" disabled={!replayable} onClick={next}><Icon name="stepForward" /></button>
        <div className="scrub">
          <div className="scrub-meta">
            <span><b>{label}</b></span>
            {shownEvent && <span>Score {formatNumber(shownEvent.current_score)}</span>}
          </div>
          <input
            type="range"
            min={0}
            max={Math.max(last, 1)}
            value={stateView === 'replay' ? currentIteration : 0}
            disabled={!replayable}
            aria-label="Replay position"
            style={{ '--fill': `${stateView === 'replay' ? percent : 0}%` } as CSSProperties}
            onChange={(event) => setIteration(Number(event.currentTarget.value))}
          />
        </div>
        <button
          className="speed"
          type="button"
          aria-label={`Playback speed ${speed}x. Change speed`}
          disabled={idle}
          onClick={() => setPlaybackSpeed(PLAYBACK_SPEEDS[(PLAYBACK_SPEEDS.indexOf(speed as (typeof PLAYBACK_SPEEDS)[number]) + 1) % PLAYBACK_SPEEDS.length])}
        >
          {speed}x
        </button>
        <Segmented label="Shown state" options={VIEW_OPTIONS} value={stateView} onChange={setStateView} disabled={idle} className="view-seg" />
      </div>
    </div>
  )
}
