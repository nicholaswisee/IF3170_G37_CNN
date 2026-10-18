import { Fragment, useReducer, useState } from 'react'
import { checkProblemLimits, totalTruckVolume } from '../api/limits'
import { formatWhole } from '../copy/format'
import type { Limits, Problem } from '../types/experiment'
import { GlassSwitch } from '../ui/GlassSwitch'
import { Icon } from '../ui/Icon'
import { Modal } from '../ui/Modal'
import { Segmented } from '../ui/Segmented'
import { useToast } from '../ui/toastContext'
import { createProblemForm, parseProblemForm, problemFormReducer, type PackageDraft, type TruckDraft } from './problemForm'

type Table = 'trucks' | 'packages'

const TRUCK_COLUMNS: [keyof TruckDraft, string][] = [['width', 'Width'], ['length', 'Length'], ['height', 'Height'], ['max_capacity', 'Max capacity kg']]
const PACKAGE_COLUMNS: [Exclude<keyof PackageDraft, 'id' | 'is_fragile'>, string][] = [['width', 'Width'], ['length', 'Length'], ['height', 'Height'], ['value', 'Value'], ['weight', 'Weight kg'], ['eta', 'ETA']]

interface ProblemEditorProps {
  initialProblem: Problem
  limits: Limits | null
  onApply: (problem: Problem) => Promise<void>
  onClose: () => void
}

/** Popup table editor for trucks and packages. The backend validates the result before it is applied. */
export function ProblemEditor({ initialProblem, limits, onApply, onClose }: ProblemEditorProps) {
  const toast = useToast()
  const [draft, dispatch] = useReducer(problemFormReducer, initialProblem, createProblemForm)
  const [table, setTable] = useState<Table>('trucks')
  const [showErrors, setShowErrors] = useState(false)
  const [applying, setApplying] = useState(false)
  const parsed = parseProblemForm(draft)
  const errors = showErrors ? parsed.errors : {}
  const volume = parsed.problem ? totalTruckVolume(parsed.problem) : null

  const apply = async () => {
    setShowErrors(true)
    const firstError = Object.entries(parsed.errors)[0]
    if (!parsed.problem || firstError) {
      if (firstError) {
        const [path, message] = firstError
        setTable(path.startsWith('packages') ? 'packages' : 'trucks')
        toast.show(`${message.replace(/\.$/, '')}. Check the highlighted field`, 'error')
      }
      return
    }
    const limitError = limits ? checkProblemLimits(parsed.problem, limits) : null
    if (limitError) {
      toast.show(limitError, 'error')
      return
    }
    setApplying(true)
    try {
      await onApply(parsed.problem)
    } finally {
      setApplying(false)
    }
  }

  const cell = (path: string, id: string, value: string, label: string, onChange: (value: string) => void, numeric = true) => (
    <td>
      <input
        id={id}
        type="text"
        inputMode={numeric ? 'decimal' : undefined}
        value={value}
        aria-label={label}
        aria-invalid={errors[path] ? true : undefined}
        title={errors[path]}
        onChange={(event) => onChange(event.currentTarget.value)}
      />
    </td>
  )

  const footer = (
    <>
      <button className="btn btn-plain" type="button" onClick={() => dispatch({ type: table === 'trucks' ? 'add-truck' : 'add-package' })}>
        <Icon name="plus" size={16} />{table === 'trucks' ? 'Add truck' : 'Add package'}
      </button>
      <span className="spacer" />
      <button className="btn btn-plain" type="button" onClick={onClose}>Cancel</button>
      <button className="btn btn-primary" type="button" disabled={applying} onClick={() => void apply()}>
        {applying && <span className="spinner light" aria-hidden="true" />}{applying ? 'Checking' : 'Apply changes'}
      </button>
    </>
  )

  return (
    <Modal title="Edit problem" onClose={onClose} footer={footer}>
      <Segmented
        label="Edit"
        className="editor-tabs"
        options={[{ value: 'trucks', label: `Trucks ${draft.trucks.length}` }, { value: 'packages', label: `Packages ${draft.packages.length}` }]}
        value={table}
        onChange={setTable}
      />
      {table === 'trucks' ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Truck ID</th>{TRUCK_COLUMNS.map(([, label]) => <th key={label}>{label}</th>)}<th><span className="visually-hidden">Remove</span></th></tr></thead>
            <tbody>
              {draft.trucks.map(({ key, values }, index) => (
                <tr key={key}>
                  {cell(`trucks.${key}.id`, `truck-${key}-id`, values.id, `Truck ${index + 1} ID`, (id) => dispatch({ type: 'update-truck', key, changes: { id } }), false)}
                  {TRUCK_COLUMNS.map(([field, label]) => (
                    <Fragment key={field}>
                      {cell(`trucks.${key}.${field}`, `truck-${key}-${field}`, values[field], `Truck ${index + 1} ${label}`, (value) => dispatch({ type: 'update-truck', key, changes: { [field]: value } }))}
                    </Fragment>
                  ))}
                  <td>
                    <button className="icon-btn" type="button" aria-label={`Remove truck ${values.id || index + 1}`} disabled={draft.trucks.length <= 1} onClick={() => dispatch({ type: 'remove-truck', key })}><Icon name="trash" size={17} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Package ID</th>{PACKAGE_COLUMNS.map(([, label]) => <th key={label}>{label}</th>)}<th>Fragile</th><th><span className="visually-hidden">Remove</span></th></tr></thead>
            <tbody>
              {draft.packages.length === 0 && <tr><td colSpan={9} className="empty">No packages yet. Add one to start.</td></tr>}
              {draft.packages.map(({ key, values }, index) => (
                <tr key={key}>
                  {cell(`packages.${key}.id`, `package-${key}-id`, values.id, `Package ${index + 1} ID`, (id) => dispatch({ type: 'update-package', key, changes: { id } }), false)}
                  {PACKAGE_COLUMNS.map(([field, label]) => (
                    <Fragment key={field}>
                      {cell(`packages.${key}.${field}`, `package-${key}-${field}`, values[field], `Package ${index + 1} ${label}`, (value) => dispatch({ type: 'update-package', key, changes: { [field]: value } }))}
                    </Fragment>
                  ))}
                  <td>
                    <GlassSwitch id={`package-${key}-fragile`} label={`Package ${index + 1} fragile`} checked={values.is_fragile} onChange={(is_fragile) => dispatch({ type: 'update-package', key, changes: { is_fragile } })} />
                  </td>
                  <td>
                    <button className="icon-btn" type="button" aria-label={`Remove package ${values.id || index + 1}`} onClick={() => dispatch({ type: 'remove-package', key })}><Icon name="trash" size={17} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="caption">
        Sizes are whole units and capacity is in kg.
        {limits && ` The backend allows up to ${limits.problem.max_trucks} trucks, ${limits.problem.max_packages} packages, and ${formatWhole(limits.problem.max_total_truck_volume)} cells of total truck volume.`}
        {volume !== null && ` This fleet uses ${formatWhole(volume)} cells.`}
      </p>
    </Modal>
  )
}
