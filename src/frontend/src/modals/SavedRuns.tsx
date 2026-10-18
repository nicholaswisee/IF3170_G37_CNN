import { ALGORITHM_LABELS, OBJECTIVE_LABELS, VARIANT_LABELS, formatNumber, formatWhole } from '../copy/format'
import type { ExperimentResult } from '../types/experiment'
import { Icon } from '../ui/Icon'
import { Modal } from '../ui/Modal'

interface SavedRunsProps {
  experiments: ExperimentResult[]
  activeId: string | null
  loading: boolean
  onRefresh: () => void
  onOpen: (experiment: ExperimentResult) => void
  onClose: () => void
}

/** Popup table of runs read from the output folder, for comparing and reopening them. */
export function SavedRuns({ experiments, activeId, loading, onRefresh, onOpen, onClose }: SavedRunsProps) {
  const refresh = (
    <button className="btn btn-plain btn-sm" type="button" disabled={loading} onClick={onRefresh}>
      {loading ? <span className="spinner" aria-hidden="true" /> : <Icon name="refresh" size={14} />}{loading ? 'Loading' : 'Refresh'}
    </button>
  )
  const topScore = Math.max(-Infinity, ...experiments.filter((run) => run.objective_mode === 'total_value').map((run) => run.best_score))
  return (
    <Modal title="Saved runs" onClose={onClose} headerExtra={refresh}>
      {experiments.length === 0 ? (
        <div className="group empty-state"><p>{loading ? 'Loading saved runs' : 'No saved runs yet. Runs with Save run turned on appear here.'}</p></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Algorithm</th><th>Variant</th><th>Objective</th><th>Seed</th><th>Best score</th><th>Runtime</th><th>Steps</th><th><span className="visually-hidden">Open</span></th></tr>
            </thead>
            <tbody>
              {experiments.map((run) => (
                <tr key={run.id} aria-current={run.id === activeId || undefined}>
                  <td>{ALGORITHM_LABELS[run.algorithm]}</td>
                  <td>{run.variant ? VARIANT_LABELS[run.variant] : 'None'}</td>
                  <td>{OBJECTIVE_LABELS[run.objective_mode]}</td>
                  <td>{run.seed}</td>
                  <td>
                    <b>{formatNumber(run.best_score)}</b>
                    {run.objective_mode === 'total_value' && run.best_score === topScore && <span className="tag green inline">Top</span>}
                  </td>
                  <td>{formatWhole(run.runtime_ms)} ms</td>
                  <td>{formatWhole(run.iterations)}</td>
                  <td>
                    <button className="btn btn-tinted btn-sm" type="button" disabled={run.id === activeId} onClick={() => onOpen(run)}>
                      {run.id === activeId ? 'Showing' : 'Open'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="caption">Opening a run loads its problem, its replay, and its charts. Top marks the highest total value score.</p>
    </Modal>
  )
}
