import { useState, type ChangeEvent } from 'react'
import { runExperiment } from '../api/client'
import { buildRunRequest } from '../api/requests'
import { useReplayStore } from '../stores/replayStore'
import type { Algorithm, ExperimentResult, Problem } from '../types/experiment'

const algorithms: { value: Algorithm; label: string }[] = [
  { value: 'hill_climbing', label: 'Hill Climbing' },
  { value: 'simulated_annealing', label: 'Simulated Annealing' },
  { value: 'genetic_algorithm', label: 'Genetic Algorithm' },
]

interface AlgorithmControlsProps {
  problem: Problem
  onExperimentReady: (experiment: ExperimentResult) => void
}

export function AlgorithmControls({ problem, onExperimentReady }: AlgorithmControlsProps) {
  const [algorithm, setAlgorithm] = useState<Algorithm>('hill_climbing')
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { isPlaying, playbackSpeed, next, pause, play, previous, setPlaybackSpeed } = useReplayStore()

  const handleAlgorithmChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setAlgorithm(event.target.value as Algorithm)
  }

  const handleSpeedChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setPlaybackSpeed(Number(event.target.value))
  }

  const handleRun = async () => {
    setIsRunning(true)
    setError(null)

    try {
      const experiment = await runExperiment(buildRunRequest({ algorithm, problem, seed: 42 }))
      onExperimentReady(experiment)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Experiment request failed')
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <section className="control-panel" aria-labelledby="algorithm-heading">
      <div className="panel-heading">
        <span className="panel-index">01</span>
        <h2 id="algorithm-heading">Algorithm console</h2>
      </div>
      <label className="field-label" htmlFor="algorithm">Search method</label>
      <select id="algorithm" value={algorithm} onChange={handleAlgorithmChange}>
        {algorithms.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <button className="run-button" type="button" onClick={() => void handleRun()} disabled={isRunning}>
        {isRunning ? 'Dispatching...' : 'Run experiment'}
      </button>
      {error && <p className="control-error" role="alert">{error}</p>}
      <div className="transport-controls" aria-label="Replay controls">
        <button type="button" onClick={previous}>Previous</button>
        <button type="button" onClick={play} disabled={isPlaying}>Play</button>
        <button type="button" onClick={pause} disabled={!isPlaying}>Pause</button>
        <button type="button" onClick={next}>Next</button>
      </div>
      <label className="field-label" htmlFor="playback-speed">Playback speed</label>
      <select id="playback-speed" value={playbackSpeed} onChange={handleSpeedChange}>
        <option value={0.5}>0.5×</option>
        <option value={1}>1×</option>
        <option value={2}>2×</option>
      </select>
    </section>
  )
}
