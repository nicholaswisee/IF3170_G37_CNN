import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type CSSProperties } from 'react'
import { getLimits, listExperiments, runExperiment, validateProblem } from './api/client'
import { bestEventIndex } from './charts/chartData'
import { ChartsView } from './charts/ChartsView'
import { ALGORITHM_LABELS, formatNumber, formatWhole } from './copy/format'
import { mockProblem } from './mocks/fleetFixture'
import { HelpSheet } from './modals/HelpSheet'
import { ProblemEditor } from './modals/ProblemEditor'
import { SavedRuns } from './modals/SavedRuns'
import { ResultsPanel } from './panels/ResultsPanel'
import { SetupPanel } from './panels/SetupPanel'
import { CAMERA_PRESETS } from './scene/cameraPresets'
import type { CameraCommands } from './scene/CameraRig'
import { FleetScene } from './scene/FleetScene'
import { LayersMenu, type LayerToggles } from './shell/LayersMenu'
import { LockBar } from './shell/LockBar'
import { MapControls } from './shell/MapControls'
import { PackageCard } from './shell/PackageCard'
import { PlaybackBar } from './shell/PlaybackBar'
import { TopBar } from './shell/TopBar'
import { packageTransitionSeconds, selectReplayState, usePlaybackTicker, useReplayStore } from './stores/replayStore'
import type { ExperimentResult, Limits, OptimizationState, Problem, RunExperimentRequest } from './types/experiment'
import { Modal } from './ui/Modal'
import { ToastProvider, ToastViewport } from './ui/toast'
import { useToast } from './ui/toastContext'
import { useGlassPointer } from './ui/useGlassPointer'
import { truckLoads, type ColorMode } from './viewer/sceneModel'

const MOBILE_QUERY = '(max-width: 760px)'
// Panel width plus the gap to the stage, kept in sync with --pw and --gap in layout.css.
const PANEL_FOOTPRINT = 364

type ModalName = 'problem' | 'runs' | 'charts' | 'help'

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

function subscribeToMobile(callback: () => void): () => void {
  const query = window.matchMedia(MOBILE_QUERY)
  query.addEventListener('change', callback)
  return () => query.removeEventListener('change', callback)
}

const isMobileNow = () => window.matchMedia(MOBILE_QUERY).matches

function Workspace() {
  const toast = useToast()
  useGlassPointer()
  usePlaybackTicker()
  const mobile = useSyncExternalStore(subscribeToMobile, isMobileNow, () => false)

  const experiment = useReplayStore((state) => state.experiment)
  const currentIteration = useReplayStore((state) => state.currentIteration)
  const stateView = useReplayStore((state) => state.stateView)
  const motionSpeed = useReplayStore((state) => state.motionSpeed)

  const [configuredProblem, setConfiguredProblem] = useState<Problem>(mockProblem)
  const [isExampleProblem, setIsExampleProblem] = useState(true)
  const [limits, setLimits] = useState<Limits | null>(null)
  const [limitsError, setLimitsError] = useState<string | null>(null)
  const [experiments, setExperiments] = useState<ExperimentResult[]>([])
  const [loadingRuns, setLoadingRuns] = useState(false)
  const [setupOpen, setSetupOpen] = useState(() => !isMobileNow())
  const [resultsOpen, setResultsOpen] = useState(() => !isMobileNow())
  const [lockedTruckId, setLockedTruckId] = useState<string | null>(null)
  const [colorMode, setColorMode] = useState<ColorMode>('identity')
  const [toggles, setToggles] = useState<LayerToggles>({ labels: true, grid: true, trail: true })
  const [glass, setGlass] = useState(0.5)
  const [cardPackageId, setCardPackageId] = useState<string | null>(null)
  const [modal, setModal] = useState<ModalName | null>(null)
  const [cameraPreset, setCameraPreset] = useState(0)
  const [running, setRunning] = useState(false)
  const camera = useRef<CameraCommands>(null)

  const problem = experiment?.problem ?? configuredProblem
  const previewState = useMemo<OptimizationState>(() => ({
    placements: configuredProblem.packages.map((pkg) => ({ package_id: pkg.id, truck_id: null, position: null, orientation: 0 })),
  }), [configuredProblem])
  const shownState = selectReplayState(experiment, currentIteration, stateView) ?? previewState
  let shownIndex = -1
  if (experiment) {
    if (stateView === 'replay') shownIndex = currentIteration
    else if (stateView === 'initial') shownIndex = 0
    else if (stateView === 'final') shownIndex = experiment.history.length - 1
    else shownIndex = bestEventIndex(experiment.history, experiment.best_score)
  }
  const shownEvent = experiment?.history[shownIndex] ?? null
  const previousState = experiment && stateView === 'replay' && currentIteration > 0
    ? experiment.history[currentIteration - 1]?.state_snapshot ?? null
    : null
  const activeLock = lockedTruckId !== null && problem.trucks.some((truck) => truck.id === lockedTruckId) ? lockedTruckId : null
  const activeCard = cardPackageId !== null && problem.packages.some((pkg) => pkg.id === cardPackageId) ? cardPackageId : null
  const lockedIndex = problem.trucks.findIndex((truck) => truck.id === activeLock)
  const loads = useMemo(() => truckLoads(problem, shownState), [problem, shownState])

  const fetchLimits = useCallback(() => getLimits().then(
    (value) => {
      setLimits(value)
      setLimitsError(null)
    },
    (error: unknown) => setLimitsError(`Could not load allowed ranges from the backend. ${messageOf(error)}`),
  ), [])

  const mergeRuns = (saved: ExperimentResult[]) => setExperiments((current) => {
    const byId = new Map(current.map((run) => [run.id, run]))
    for (const run of saved) if (!byId.has(run.id)) byId.set(run.id, run)
    return [...byId.values()]
  })

  // Initial load. The active flag keeps a doubled development effect from announcing twice.
  useEffect(() => {
    let active = true
    void fetchLimits()
    listExperiments().then(
      ({ experiments: saved }) => {
        if (!active) return
        mergeRuns(saved)
        if (saved.length > 0) toast.show(`${saved.length} saved runs found. Open them from Saved runs`, 'info', 4200)
      },
      (error: unknown) => {
        if (active) toast.show(`Could not load saved runs. ${messageOf(error)}`, 'error')
      },
    )
    return () => {
      active = false
    }
  }, [fetchLimits, toast])

  const openPanel = (side: 'setup' | 'results', open: boolean) => {
    if (side === 'setup') setSetupOpen(open)
    else setResultsOpen(open)
    if (open && mobile) (side === 'setup' ? setResultsOpen : setSetupOpen)(false)
  }

  const lockTruck = (truckId: string) => {
    if (activeLock === null) toast.show(`${truckId} view. Drag to orbit this truck and press Esc to leave`, 'info', 3600)
    setLockedTruckId(truckId)
  }

  const stepTruck = (direction: 1 | -1) => {
    const trucks = problem.trucks
    if (trucks.length === 0) return
    const next = lockedIndex < 0
      ? (direction > 0 ? 0 : trucks.length - 1)
      : (lockedIndex + direction + trucks.length) % trucks.length
    lockTruck(trucks[next].id)
  }

  const focusDock = () => {
    if (activeLock !== null) setLockedTruckId(null)
    else camera.current?.focusDock()
  }

  const search = (query: string) => {
    const needle = query.toLowerCase()
    const truck = problem.trucks.find((item) => item.id.toLowerCase() === needle)
    if (truck) {
      lockTruck(truck.id)
      return
    }
    const pkg = problem.packages.find((item) => item.id.toLowerCase() === needle)
    if (!pkg) {
      toast.show(`No package or truck is named ${query}`, 'error')
      return
    }
    const placement = shownState.placements.find((item) => item.package_id === pkg.id)
    if (placement?.truck_id) setLockedTruckId(placement.truck_id)
    else focusDock()
    setCardPackageId(pkg.id)
  }

  const run = async (request: RunExperimentRequest, label: string) => {
    setRunning(true)
    const id = toast.show(`Running ${label}`, 'progress')
    try {
      const result = await runExperiment(request)
      setExperiments((current) => [result, ...current.filter((item) => item.id !== result.id)])
      useReplayStore.getState().setExperiment(result)
      setCardPackageId(null)
      openPanel('results', true)
      toast.update(id, `Finished. Best score ${formatNumber(result.best_score)} in ${formatWhole(result.runtime_ms)} ms`, 'success', 4200)
      if (result.history.length > 1 && result.history.some((event) => event.state_snapshot !== null)) useReplayStore.getState().play()
    } catch (error) {
      toast.update(id, `${label} failed. ${messageOf(error)}`, 'error')
    } finally {
      setRunning(false)
    }
  }

  const applyProblem = async (next: Problem) => {
    try {
      await validateProblem(next)
    } catch (error) {
      toast.show(`The backend rejected this problem. ${messageOf(error)}`, 'error')
      return
    }
    setConfiguredProblem(next)
    setIsExampleProblem(false)
    setLockedTruckId(null)
    setCardPackageId(null)
    useReplayStore.getState().reset()
    setModal(null)
    toast.show(`Problem applied. ${next.trucks.length} trucks and ${next.packages.length} packages are ready`, 'success')
  }

  const previewProblem = () => {
    useReplayStore.getState().reset()
    setCardPackageId(null)
    toast.show('Showing the configured problem. Every package starts in the Dock', 'info')
  }

  const openRun = (selected: ExperimentResult) => {
    useReplayStore.getState().setExperiment(selected)
    setCardPackageId(null)
    setModal(null)
    openPanel('results', true)
    toast.show(`Opened the ${ALGORITHM_LABELS[selected.algorithm]} run with seed ${selected.seed}`, 'success')
  }

  const refreshRuns = () => {
    setLoadingRuns(true)
    listExperiments()
      .then(({ experiments: saved }) => mergeRuns(saved), (error: unknown) => toast.show(`Could not load saved runs. ${messageOf(error)}`, 'error'))
      .finally(() => setLoadingRuns(false))
  }

  // Keyboard shortcuts. Escape closes the top layer first; other keys stay out of text fields.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target instanceof HTMLElement ? event.target : null
      if (event.key === 'Escape') {
        if (modal) setModal(null)
        else if (cardPackageId) setCardPackageId(null)
        else if (lockedTruckId) setLockedTruckId(null)
        return
      }
      if (modal || target?.closest('input, textarea, select, [contenteditable="true"]')) return
      if (target?.closest('button') && (event.key === ' ' || event.key === 'Enter')) return
      const replay = useReplayStore.getState()
      if (event.key === ' ') {
        event.preventDefault()
        if (replay.isPlaying) replay.pause()
        else replay.play()
      } else if (event.key === 'ArrowRight') replay.next()
      else if (event.key === 'ArrowLeft') replay.previous()
      else if (event.key === ']') stepTruck(1)
      else if (event.key === '[') stepTruck(-1)
      else if (event.key === 'f' || event.key === 'F') camera.current?.fit()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const covered = mobile ? 0 : (setupOpen ? PANEL_FOOTPRINT : 0) + (resultsOpen ? PANEL_FOOTPRINT : 0)
  const viewShift = mobile ? 0 : ((setupOpen ? PANEL_FOOTPRINT : 0) - (resultsOpen ? PANEL_FOOTPRINT : 0)) / 2
  const appClass = ['app', setupOpen && 'setup-open', resultsOpen && 'results-open'].filter(Boolean).join(' ')
  const lockedTruck = lockedIndex >= 0 ? problem.trucks[lockedIndex] : null

  return (
    <div className={appClass} style={{ '--glass-alpha': glass } as CSSProperties}>
      <FleetScene
        problem={problem}
        state={shownState}
        previousState={previousState}
        lockedTruckId={activeLock}
        selectedPackageId={activeCard}
        colorMode={colorMode}
        showLabels={toggles.labels}
        showGrid={toggles.grid}
        showTrail={toggles.trail}
        transitionSeconds={packageTransitionSeconds(motionSpeed)}
        cameraPreset={cameraPreset}
        viewShift={viewShift}
        coveredWidth={covered}
        cameraCommands={camera}
        onSelectTruck={lockTruck}
        onSelectPackage={setCardPackageId}
        onFocusDock={focusDock}
      />

      <TopBar
        trucks={problem.trucks}
        packageIds={problem.packages.map((pkg) => pkg.id)}
        lockedTruckId={activeLock}
        fragileHighlighted={colorMode === 'fragile'}
        resultsOpen={resultsOpen}
        onToggleSetup={() => openPanel('setup', !setupOpen)}
        onToggleResults={() => openPanel('results', !resultsOpen)}
        onFreeView={() => setLockedTruckId(null)}
        onLockTruck={lockTruck}
        onToggleFragile={() => setColorMode((mode) => mode === 'fragile' ? 'identity' : 'fragile')}
        onSearch={search}
        onOpenRuns={() => setModal('runs')}
        onOpenHelp={() => setModal('help')}
      />

      <SetupPanel
        open={setupOpen}
        problem={configuredProblem}
        isExampleProblem={isExampleProblem}
        viewingRun={experiment !== null}
        limits={limits}
        limitsError={limitsError}
        running={running}
        onRetryLimits={() => void fetchLimits()}
        onEditProblem={() => setModal('problem')}
        onPreviewProblem={previewProblem}
        onRun={(request, label) => void run(request, label)}
      />

      <ResultsPanel
        open={resultsOpen}
        experiment={experiment}
        problem={problem}
        state={shownState}
        shownEvent={shownEvent}
        shownIndex={shownIndex}
        stateView={stateView}
        colorMode={colorMode}
        onClose={() => openPanel('results', false)}
        onJump={(index) => useReplayStore.getState().setIteration(index)}
        onSelectPackage={(packageId) => {
          setCardPackageId(packageId)
          focusDock()
        }}
        onExpandCharts={() => setModal('charts')}
      />

      {lockedTruck && (
        <LockBar
          truck={lockedTruck}
          position={lockedIndex + 1}
          total={problem.trucks.length}
          loadWeight={loads[lockedTruck.id]?.weight ?? 0}
          onPrevious={() => stepTruck(-1)}
          onNext={() => stepTruck(1)}
          onExit={() => setLockedTruckId(null)}
        />
      )}

      <PlaybackBar shownEvent={shownEvent} />
      <ToastViewport />

      <LayersMenu
        colorMode={colorMode}
        onColorMode={setColorMode}
        toggles={toggles}
        onToggle={(key, value) => setToggles((current) => ({ ...current, [key]: value }))}
        glass={glass}
        onGlass={setGlass}
      />
      <MapControls
        onFit={() => camera.current?.fit()}
        onZoomIn={() => camera.current?.zoom(0.78)}
        onZoomOut={() => camera.current?.zoom(1.28)}
        onNextView={() => {
          const next = (cameraPreset + 1) % CAMERA_PRESETS.length
          setCameraPreset(next)
          toast.show(CAMERA_PRESETS[next].name, 'info', 1400)
        }}
        view={CAMERA_PRESETS[cameraPreset]}
        nextViewName={CAMERA_PRESETS[(cameraPreset + 1) % CAMERA_PRESETS.length].name}
      />

      {activeCard && <PackageCard problem={problem} state={shownState} packageId={activeCard} colorMode={colorMode} onClose={() => setCardPackageId(null)} />}

      {modal === 'problem' && <ProblemEditor initialProblem={configuredProblem} limits={limits} onApply={applyProblem} onClose={() => setModal(null)} />}
      {modal === 'runs' && (
        <SavedRuns experiments={experiments} activeId={experiment?.id ?? null} loading={loadingRuns} onRefresh={refreshRuns} onOpen={openRun} onClose={() => setModal(null)} />
      )}
      {modal === 'charts' && experiment && (
        <Modal title="Charts" onClose={() => setModal(null)}>
          <ChartsView experiment={experiment} cursor={shownEvent?.iteration ?? null} large />
        </Modal>
      )}
      {modal === 'help' && <HelpSheet onClose={() => setModal(null)} />}
    </div>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <Workspace />
    </ToastProvider>
  )
}
