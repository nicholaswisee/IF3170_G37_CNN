import { useEffect, useState } from 'react'
import { healthCheck } from './api/client'
import { AlgorithmControls } from './components/AlgorithmControls'
import { IterationInspector } from './components/IterationInspector'
import { ObjectiveChart } from './components/ObjectiveChart'
import { TruckScene } from './components/TruckScene/TruckScene'
import { useReplayStore } from './stores/replayStore'
import type { ExperimentResult } from './types/experiment'

type ConnectionState = 'checking' | 'connected' | 'disconnected'

export default function App() {
  const [connection, setConnection] = useState<ConnectionState>('checking')
  const setExperiment = useReplayStore((state) => state.setExperiment)

  useEffect(() => {
    let active = true

    healthCheck()
      .then(() => { if (active) setConnection('connected') })
      .catch(() => { if (active) setConnection('disconnected') })

    return () => { active = false }
  }, [])

  const handleExperimentReady = (experiment: ExperimentResult) => {
    setExperiment(experiment)
  }

  const statusLabel = connection === 'checking' ? 'Checking connection' : connection === 'connected' ? 'Connected' : 'Disconnected'

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">mejirowise / terminal 01</p>
          <h1>Container optimization visualizer</h1>
        </div>
        <p className={`connection connection--${connection}`} aria-live="polite">
          <span aria-hidden="true" /> Backend: {statusLabel}
        </p>
      </header>
      <div className="workspace">
        <section className="scene-panel" aria-label="Truck scene">
          <TruckScene />
        </section>
        <aside className="side-panel">
          <AlgorithmControls onExperimentReady={handleExperimentReady} />
          <IterationInspector />
        </aside>
      </div>
      <ObjectiveChart />
    </main>
  )
}
