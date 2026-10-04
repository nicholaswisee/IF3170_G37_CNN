import { useState } from 'react'
import { AlgorithmControls } from './components/AlgorithmControls'
import { IterationInspector } from './components/IterationInspector'
import { ObjectiveChart } from './components/ObjectiveChart'
import { TruckScene } from './components/TruckScene/TruckScene'
import { TruckSelector } from './components/TruckScene/TruckSelector'
import { mockProblem, mockStates } from './mocks/fleetFixture'
import { useReplayStore } from './stores/replayStore'
import type { ExperimentResult } from './types/experiment'

export default function App() {
  const experiment = useReplayStore((state) => state.experiment)
  const setExperiment = useReplayStore((state) => state.setExperiment)
  // The mock fleet is shown until a run returns; it is also the problem sent with each run.
  const problem = experiment?.problem ?? mockProblem
  const viewedState = experiment?.best_state ?? mockStates.best
  const [selectedTruckId, setSelectedTruckId] = useState(mockProblem.trucks[0].id)
  const activeTruckId = problem.trucks.some((truck) => truck.id === selectedTruckId) ? selectedTruckId : problem.trucks[0].id

  const handleExperimentReady = (experiment: ExperimentResult) => {
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
          <TruckSelector trucks={problem.trucks} selectedTruckId={activeTruckId} onSelect={setSelectedTruckId} />
          <TruckScene problem={problem} state={viewedState} truckId={activeTruckId} />
        </section>
        <aside className="side-panel">
          <AlgorithmControls problem={mockProblem} onExperimentReady={handleExperimentReady} />
          <IterationInspector />
        </aside>
      </div>
      <ObjectiveChart />
    </main>
  )
}
