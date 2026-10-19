import { useState } from 'react'
import { progressLabel } from '../charts/chartData'
import { ChartsView } from '../charts/ChartsView'
import { ALGORITHM_LABELS, OBJECTIVE_LABELS, ORIENTATION_NAMES, VARIANT_LABELS, describeMove, formatCompact, formatNumber, formatWhole, moveRoute, placementText } from '../copy/format'
import type { StateView } from '../stores/replayStore'
import type { ExperimentResult, OptimizationState, Problem, SearchEvent } from '../types/experiment'
import { Icon } from '../ui/Icon'
import { Segmented } from '../ui/Segmented'
import { outsidePackages, packageColor, truckLoads, type ColorMode } from '../viewer/sceneModel'
import { loadedCount, runMetrics } from './runMetrics'

type Tab = 'summary' | 'charts' | 'step' | 'outside'

const VIEW_NAMES: Record<StateView, string> = { replay: 'Replay', initial: 'Initial state', final: 'Final state', best: 'Best state' }

function Rows({ rows }: { rows: [string, string][] }) {
  return (
    <div className="group">
      {rows.map(([label, value]) => (
        <div className="row" key={label}>
          <span className="row-label"><span>{label}</span></span>
          <span className="row-value">{value}</span>
        </div>
      ))}
    </div>
  )
}

export function FleetLoad({ problem, state, caption }: { problem: Problem; state: OptimizationState; caption: string }) {
  const loads = truckLoads(problem, state)
  return (
    <section>
      <div className="section-title"><span>Fleet load</span><span className="section-note">{caption}</span></div>
      <div className="group">
        {problem.trucks.map((truck) => {
          const load = loads[truck.id]
          const share = truck.max_capacity > 0 ? Math.min(100, (load.weight / truck.max_capacity) * 100) : 0
          return (
            <div className="load-row" key={truck.id}>
              <div className="load-top">
                <span>{truck.id}</span>
                <small>{formatNumber(load.weight)} of {formatWhole(truck.max_capacity)} kg, {load.count} loaded</small>
              </div>
              <span className="load-bar" aria-hidden="true"><i className={share > 85 ? 'high' : undefined} style={{ width: `${share}%` }} /></span>
            </div>
          )
        })}
      </div>
      <p className="caption">Weights are added up from the packages in the state you are viewing.</p>
    </section>
  )
}

export function SummaryTab({ experiment, problem, state, viewCaption }: { experiment: ExperimentResult | null; problem: Problem; state: OptimizationState; viewCaption: string }) {
  if (!experiment) {
    return (
      <>
        <div className="group empty-state"><p>Run an algorithm or open a saved run to see its scores here.</p></div>
        <FleetLoad problem={problem} state={state} caption="Preview" />
      </>
    )
  }
  const stats: [string, number, OptimizationState, boolean][] = [
    ['Initial', experiment.initial_score, experiment.initial_state, false],
    ['Final', experiment.final_score, experiment.final_state, false],
    ['Best', experiment.best_score, experiment.best_state, true],
  ]
  return (
    <>
      <div className="stat-grid">
        {stats.map(([label, score, stored, best]) => (
          <div className={best ? 'stat best' : 'stat'} key={label}>
            <span>{label}</span>
            <b>{formatNumber(score)}</b>
            <span>{loadedCount(stored)} loaded</span>
          </div>
        ))}
      </div>
      <Rows rows={runMetrics(experiment)} />
      <FleetLoad problem={problem} state={state} caption={viewCaption} />
    </>
  )
}

export function StepTab({ experiment, event, index, onJump }: { experiment: ExperimentResult | null; event: SearchEvent | null; index: number; onJump: (index: number) => void }) {
  if (!experiment || !event) return <div className="group empty-state"><p>Step details appear here while you replay a run.</p></div>
  const unit = progressLabel(experiment.algorithm)
  const isGenetic = experiment.algorithm === 'genetic_algorithm'
  const rows: [string, string][] = []
  if (event.candidate_score !== null) rows.push(['Candidate score', formatNumber(event.candidate_score)])
  rows.push([isGenetic ? 'Max fitness' : 'Current score', formatNumber(event.current_score)])
  if (event.mean_score !== null) rows.push(['Mean fitness', formatNumber(event.mean_score)])
  rows.push(['Best so far', formatNumber(event.best_score)])
  if (event.temperature !== null) rows.push(['Temperature', formatCompact(event.temperature)])
  if (event.acceptance_probability !== null) rows.push(['Acceptance probability', formatCompact(event.acceptance_probability)])
  const recent = experiment.history.slice(Math.max(0, index - 7), index + 1)
    .map((item, offset) => ({ item, at: Math.max(0, index - 7) + offset }))
    .filter(({ item }) => item.move !== null)
    .reverse()

  let sentence = isGenetic ? `Best individual of generation ${event.iteration}.` : 'Starting state. No move yet.'
  if (event.move) sentence = describeMove(event.move)
  else if (!isGenetic && event.iteration > 0) sentence = event.accepted === false ? 'No candidate was accepted in this step.' : 'No move was recorded for this step.'

  return (
    <>
      <div className="group step-hero">
        <div className="tags">
          {event.move && <span className="tag blue">{event.move.type}</span>}
          {event.accepted !== null && <span className={event.accepted ? 'tag green' : 'tag red'}>{event.accepted ? 'Accepted' : 'Rejected'}</span>}
          <span className="tag">{unit} {event.iteration}</span>
        </div>
        <p>{sentence}</p>
      </div>
      {event.move && (
        <div className="group">
          {event.move.package_ids.map((id, position) => {
            const before = event.move?.before[position]
            const after = event.move?.after[position]
            return (
              <div className="row" key={id}>
                <span className="row-label">
                  <span>{id}</span>
                  {before && <small>From {placementText(before)}, {ORIENTATION_NAMES[before.orientation]}</small>}
                  {after && <small>To {placementText(after)}, {ORIENTATION_NAMES[after.orientation]}</small>}
                </span>
              </div>
            )
          })}
        </div>
      )}
      <Rows rows={rows} />
      {!isGenetic && (
        <section>
          <div className="section-title"><span>Recent moves</span></div>
          <div className="group recent">
            {recent.length === 0 ? <p className="empty">Moves will show up here.</p> : recent.map(({ item, at }) => item.move && (
              <button key={at} type="button" aria-current={at === index} onClick={() => onJump(at)}>
                <span className="num">{item.iteration}</span>
                <span className={item.accepted === false ? 'tag red' : 'tag'}>{item.move.type}</span>
                <span className="ids">{item.move.package_ids.join(', ')}</span>
                <span className="route">{moveRoute(item.move)}</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </>
  )
}

export function OutsideTab({ problem, state, colorMode, onSelect }: { problem: Problem; state: OptimizationState; colorMode: ColorMode; onSelect: (packageId: string) => void }) {
  const outside = outsidePackages(problem, state)
  return (
    <>
      <div className="group">
        {outside.length === 0 ? <p className="empty">Every package is loaded.</p> : outside.map(({ pkg, index, placement }) => (
          <button className="list-row" type="button" key={pkg.id} onClick={() => onSelect(pkg.id)}>
            <span className="swatch" style={{ background: packageColor(problem, index, colorMode) }} aria-hidden="true" />
            <span className="list-main">
              <b>{pkg.id}</b>
              <small>{pkg.width} × {pkg.length} × {pkg.height}, value {formatNumber(pkg.value)}, {formatNumber(pkg.weight)} kg, ETA {pkg.eta}, {ORIENTATION_NAMES[placement?.orientation ?? 0]}</small>
            </span>
            {pkg.is_fragile && <span className="tag red">Fragile</span>}
          </button>
        ))}
      </div>
      <p className="caption">Outside packages wait in the Dock in front of the trucks. They never get a position inside a truck.</p>
    </>
  )
}

interface ResultsPanelProps {
  open: boolean
  experiment: ExperimentResult | null
  problem: Problem
  state: OptimizationState
  shownEvent: SearchEvent | null
  shownIndex: number
  stateView: StateView
  colorMode: ColorMode
  onClose: () => void
  onJump: (index: number) => void
  onSelectPackage: (packageId: string) => void
  onExpandCharts: () => void
}

/** Right panel: scores, charts, the current step, and outside packages for the viewed run. */
export function ResultsPanel({ open, experiment, problem, state, shownEvent, shownIndex, stateView, colorMode, onClose, onJump, onSelectPackage, onExpandCharts }: ResultsPanelProps) {
  const [tab, setTab] = useState<Tab>('summary')
  const outsideCount = outsidePackages(problem, state).length
  const tabs: { value: Tab; label: string }[] = [
    { value: 'summary', label: 'Summary' },
    { value: 'charts', label: 'Charts' },
    { value: 'step', label: 'Step' },
    { value: 'outside', label: `Outside ${outsideCount}` },
  ]
  const unit = progressLabel(experiment?.algorithm)
  const viewCaption = stateView === 'replay' && shownEvent ? `${unit} ${shownEvent.iteration}` : VIEW_NAMES[stateView]

  return (
    <aside className="panel panel-right glass" aria-label="Results" inert={!open}>
      <div className="panel-head">
        <h2>Results</h2>
        <button className="icon-btn" type="button" aria-label="Hide Results" onClick={onClose}><Icon name="close" /></button>
      </div>
      {experiment && (
        <div className="panel-tags">
          <span className="tag blue">{ALGORITHM_LABELS[experiment.algorithm]}</span>
          {experiment.variant && <span className="tag">{VARIANT_LABELS[experiment.variant]}</span>}
          <span className="tag">{OBJECTIVE_LABELS[experiment.objective_mode]}</span>
          <span className="tag">Seed {experiment.seed}</span>
        </div>
      )}
      <div className="panel-tabs"><Segmented<Tab> label="Result view" options={tabs} value={tab} onChange={setTab} /></div>
      <div className="panel-body">
        {tab === 'summary' && <SummaryTab experiment={experiment} problem={problem} state={state} viewCaption={viewCaption} />}
        {tab === 'charts' && (experiment
          ? <ChartsView experiment={experiment} cursor={shownEvent?.iteration ?? null} onExpand={onExpandCharts} />
          : <div className="group empty-state"><p>Charts appear after a run finishes.</p></div>)}
        {tab === 'step' && <StepTab experiment={experiment} event={shownEvent} index={shownIndex} onJump={onJump} />}
        {tab === 'outside' && <OutsideTab problem={problem} state={state} colorMode={colorMode} onSelect={onSelectPackage} />}
      </div>
    </aside>
  )
}
