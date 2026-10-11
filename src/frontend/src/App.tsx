import { useCallback, useEffect, useState } from 'react'
import { listExperiments } from './api/client'
import { AlgorithmControls } from './components/AlgorithmControls'
import { IterationInspector } from './components/IterationInspector'
import { ObjectiveChart } from './components/ObjectiveChart'
import { ExperimentComparisonTable, ResultSummary, RunSelector } from './components/ResultComparison'
import { TruckScene } from './components/TruckScene/TruckScene'
import { TruckSelector } from './components/TruckScene/TruckSelector'
import { mockProblem, mockStates } from './mocks/fleetFixture'
import { selectReplayState, useReplayStore } from './stores/replayStore'
import type { ExperimentResult } from './types/experiment'

export default function App() {
  const experiment = useReplayStore((state) => state.experiment)
  const currentIteration = useReplayStore((state) => state.currentIteration)
  const setExperiment = useReplayStore((state) => state.setExperiment)
  const [experiments, setExperiments] = useState<ExperimentResult[]>([])
  const [listError, setListError] = useState<string | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  // The mock fleet is shown until a run returns; it is also the problem sent with each run.
  const problem = experiment?.problem ?? mockProblem
  const viewedState = selectReplayState(experiment, currentIteration) ?? mockStates.best
  const [selectedTruckId, setSelectedTruckId] = useState(mockProblem.trucks[0].id)
  const activeTruckId = problem.trucks.some((truck) => truck.id === selectedTruckId) ? selectedTruckId : problem.trucks[0].id

  const refreshExperiments = useCallback(async () => {
    setIsRefreshing(true)
    setListError(null)
    try {
      const response = await listExperiments()
      setExperiments((current) => {
        const byId = new Map(current.map((run) => [run.id, run]))
        for (const run of response.experiments) byId.set(run.id, run)
        return [...byId.values()]
      })
      if (!useReplayStore.getState().experiment && response.experiments[0]) {
        setExperiment(response.experiments[0])
      }
    } catch (caught) {
      setListError(caught instanceof Error ? caught.message : 'Could not load experiment runs.')
    } finally {
      setIsRefreshing(false)
    }
  }, [setExperiment])

  useEffect(() => {
    void refreshExperiments()
  }, [refreshExperiments])

  const handleExperimentReady = (experiment: ExperimentResult) => {
    setExperiments((current) => [experiment, ...current.filter((run) => run.id !== experiment.id)])
    setExperiment(experiment)
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">mejirowise / terminal 01</p>
          <h1>Container optimization visualizer</h1>
        </div>
      </header>
      <div className="workspace">
        <section className="scene-panel" aria-label="Truck scene">
          <RunSelector experiments={experiments} selectedId={experiment?.id ?? ''} onSelect={setExperiment} />
          <TruckSelector trucks={problem.trucks} selectedTruckId={activeTruckId} onSelect={setSelectedTruckId} />
          <TruckScene problem={problem} state={viewedState} truckId={activeTruckId} />
        </section>
        <aside className="side-panel">
          <AlgorithmControls problem={mockProblem} onExperimentReady={handleExperimentReady} />
          <IterationInspector />
        </aside>
      </div>
      <div className="run-list-toolbar">
        <button type="button" onClick={() => void refreshExperiments()} disabled={isRefreshing}>
          {isRefreshing ? 'Refreshing…' : 'Refresh saved runs'}
        </button>
        {listError && <p className="control-error" role="alert">{listError}</p>}
      </div>
      <ExperimentComparisonTable experiments={experiments} selectedId={experiment?.id ?? ''} onSelect={setExperiment} />
      <ResultSummary experiment={experiment} />
      <ObjectiveChart />
    </main>
  )
}
