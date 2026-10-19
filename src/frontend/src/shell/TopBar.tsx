import { useId, useState } from 'react'
import type { TruckSpec } from '../types/experiment'
import { Icon } from '../ui/Icon'

interface TopBarProps {
  trucks: TruckSpec[]
  packageIds: string[]
  lockedTruckId: string | null
  fragileHighlighted: boolean
  resultsOpen: boolean
  onToggleSetup: () => void
  onToggleResults: () => void
  onFreeView: () => void
  onLockTruck: (truckId: string) => void
  onToggleFragile: () => void
  onSearch: (query: string) => void
  onOpenRuns: () => void
  onOpenHelp: () => void
}

/** Google Maps style top row: search pill, camera focus chips, and round glass buttons. */
export function TopBar({
  trucks, packageIds, lockedTruckId, fragileHighlighted, resultsOpen,
  onToggleSetup, onToggleResults, onFreeView, onLockTruck, onToggleFragile, onSearch, onOpenRuns, onOpenHelp,
}: TopBarProps) {
  const [query, setQuery] = useState('')
  const listId = useId()

  const submit = (value: string) => {
    if (value.trim() === '') return
    onSearch(value.trim())
    setQuery('')
  }

  return (
    <header className="topbar">
      <div className="search-pill glass">
        <button className="icon-btn interactive" type="button" aria-label="Show or hide Setup" onClick={onToggleSetup}><Icon name="menu" /></button>
        <span className="brand">Mejiro Express</span>
        <label className="search">
          <Icon name="search" size={17} />
          <input
            type="text"
            value={query}
            placeholder="Search package or truck"
            aria-label="Search package or truck"
            list={listId}
            autoComplete="off"
            onChange={(event) => {
              // Picking a suggestion from the list searches right away.
              if ((event.nativeEvent as InputEvent).inputType === 'insertReplacementText') submit(event.currentTarget.value)
              else setQuery(event.currentTarget.value)
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') submit(event.currentTarget.value)
            }}
          />
          <datalist id={listId}>
            {[...trucks.map((truck) => truck.id), ...packageIds].map((id) => <option key={id} value={id} />)}
          </datalist>
        </label>
      </div>
      <nav className="chips" aria-label="Camera focus">
        <button className="chip glass interactive" type="button" aria-pressed={lockedTruckId === null} onClick={onFreeView}>
          <Icon name="fit" size={16} />All trucks
        </button>
        {trucks.map((truck) => (
          <button key={truck.id} className="chip glass interactive" type="button" aria-pressed={lockedTruckId === truck.id} onClick={() => onLockTruck(truck.id)}>
            <Icon name="truck" size={16} />{truck.id}
          </button>
        ))}
        <span className="chip-separator" aria-hidden="true" />
        <button className="chip glass interactive" type="button" aria-pressed={fragileHighlighted} onClick={onToggleFragile}>
          <Icon name="fragile" size={16} />Fragile
        </button>
      </nav>
      <div className="top-actions">
        <button className="icon-btn round glass interactive" type="button" aria-label="Saved runs" title="Saved runs" onClick={onOpenRuns}><Icon name="history" /></button>
        <button className="icon-btn round glass interactive" type="button" aria-label={resultsOpen ? 'Hide Results' : 'Show Results'} title="Results" aria-pressed={resultsOpen} onClick={onToggleResults}><Icon name="panel" /></button>
        <button className="icon-btn round glass interactive" type="button" aria-label="Controls and shortcuts" title="Controls and shortcuts" onClick={onOpenHelp}><Icon name="help" /></button>
      </div>
    </header>
  )
}
