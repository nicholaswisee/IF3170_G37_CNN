import { useState, type ChangeEvent, type FormEvent } from 'react'
import { runExperiment } from '../api/client'
import { buildRunRequest, defaultSimulatedAnnealingParameters, validateGeneticAlgorithmInput, validateSimulatedAnnealingInput, validateSeed } from '../api/requests'
import { AnnealingParameters, type AnnealingFormValues } from './AnnealingParameters'
import { useReplayStore } from '../stores/replayStore'
import type { ExperimentResult, Problem } from '../types/experiment'

const algorithms = [
  { value: 'hill_climbing', label: 'Hill Climbing' },
  { value: 'genetic_algorithm', label: 'Genetic Algorithm' },
  { value: 'simulated_annealing', label: 'Simulated Annealing' },
] as const

interface AlgorithmControlsProps {
  problem: Problem
  onExperimentReady: (experiment: ExperimentResult) => void
}

export function AlgorithmControls({ problem, onExperimentReady }: AlgorithmControlsProps) {
  const [algorithm, setAlgorithm] = useState<(typeof algorithms)[number]['value']>('genetic_algorithm')
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [populationSize, setPopulationSize] = useState('6')
  const [generations, setGenerations] = useState('5')
  const [crossoverProbability, setCrossoverProbability] = useState('0.8')
  const [mutationProbability, setMutationProbability] = useState('0.2')
  const [seed, setSeed] = useState('42')
  const [annealing, setAnnealing] = useState<AnnealingFormValues>({
    initial_temperature: '',
    alpha: String(defaultSimulatedAnnealingParameters.alpha),
    min_temperature: String(defaultSimulatedAnnealingParameters.min_temperature),
    max_iterations: String(defaultSimulatedAnnealingParameters.max_iterations),
    stuck_patience: String(defaultSimulatedAnnealingParameters.stuck_patience),
  })
  const { isPlaying, playbackSpeed, next, pause, play, previous, setPlaybackSpeed } = useReplayStore()

  const handleAlgorithmChange = (event: ChangeEvent<HTMLSelectElement>) => {
    if (algorithms.some(({ value }) => value === event.target.value)) {
      setAlgorithm(event.target.value as (typeof algorithms)[number]['value'])
    }
  }

  const handleSpeedChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setPlaybackSpeed(Number(event.target.value))
  }

  const handleRun = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const inputValues = algorithm === 'genetic_algorithm'
      ? [populationSize, generations, crossoverProbability, mutationProbability, seed]
      : algorithm === 'simulated_annealing'
        ? [annealing.alpha, annealing.min_temperature, annealing.max_iterations, annealing.stuck_patience, seed]
        : [seed]
    if (inputValues.some((value) => value === '')) {
      setError('All numeric fields are required.')
      return
    }
    const numericSeed = Number(seed)
    const annealingParameters = {
      initial_temperature: annealing.initial_temperature.trim() === '' ? null : Number(annealing.initial_temperature),
      alpha: Number(annealing.alpha),
      min_temperature: Number(annealing.min_temperature),
      max_iterations: Number(annealing.max_iterations),
      stuck_patience: Number(annealing.stuck_patience),
    }
    const validationError = algorithm === 'genetic_algorithm'
      ? validateGeneticAlgorithmInput({
        population_size: Number(populationSize),
        generations: Number(generations),
        crossover_probability: Number(crossoverProbability),
        mutation_probability: Number(mutationProbability),
        seed: numericSeed,
      })
      : algorithm === 'simulated_annealing'
        ? validateSimulatedAnnealingInput({ ...annealingParameters, seed: numericSeed })
        : validateSeed(numericSeed)
    if (validationError) {
      setError(validationError)
      return
    }
    setIsRunning(true)
    setError(null)

    try {
      const experiment = await runExperiment(buildRunRequest({
        algorithm,
        problem,
        seed: numericSeed,
        persist: false,
        ...(algorithm === 'simulated_annealing' ? { simulatedAnnealingParameters: annealingParameters } : {}),
        ...(algorithm === 'genetic_algorithm' ? {
          geneticAlgorithmParameters: {
            population_size: Number(populationSize),
            generations: Number(generations),
            crossover_probability: Number(crossoverProbability),
            mutation_probability: Number(mutationProbability),
            elite_count: 1,
          },
        } : {}),
      }))
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
      <form onSubmit={(event) => void handleRun(event)}>
        <label className="field-label" htmlFor="algorithm">Search method</label>
        <select id="algorithm" value={algorithm} onChange={handleAlgorithmChange}>
          {algorithms.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        {algorithm === 'genetic_algorithm' && (
          <>
            <label className="field-label" htmlFor="population-size">Population size (2–100)</label>
            <input id="population-size" type="number" min={2} max={100} step={1} required value={populationSize} onChange={(event) => setPopulationSize(event.currentTarget.value)} />
            <label className="field-label" htmlFor="generations">Generations (1–200)</label>
            <input id="generations" type="number" min={1} max={200} step={1} required value={generations} onChange={(event) => setGenerations(event.currentTarget.value)} />
            <label className="field-label" htmlFor="crossover-probability">Crossover probability (0–1)</label>
            <input id="crossover-probability" type="number" min={0} max={1} step="any" required value={crossoverProbability} onChange={(event) => setCrossoverProbability(event.currentTarget.value)} />
            <label className="field-label" htmlFor="mutation-probability">Mutation probability (0–1)</label>
            <input id="mutation-probability" type="number" min={0} max={1} step="any" required value={mutationProbability} onChange={(event) => setMutationProbability(event.currentTarget.value)} />
          </>
        )}
        {algorithm === 'simulated_annealing' && (
          <AnnealingParameters values={annealing} onChange={(field, value) => setAnnealing((previous) => ({ ...previous, [field]: value }))} />
        )}
        <label className="field-label" htmlFor="seed">Seed (safe integer)</label>
        <input id="seed" type="number" min={Number.MIN_SAFE_INTEGER} max={Number.MAX_SAFE_INTEGER} step={1} required value={seed} onChange={(event) => setSeed(event.currentTarget.value)} />
        <button className="run-button" type="submit" disabled={isRunning}>
          {isRunning ? 'Dispatching...' : 'Run experiment'}
        </button>
      </form>
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
