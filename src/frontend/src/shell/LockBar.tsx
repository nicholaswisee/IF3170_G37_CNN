import { formatWhole } from '../copy/format'
import type { TruckSpec } from '../types/experiment'
import { Icon } from '../ui/Icon'

interface LockBarProps {
  truck: TruckSpec
  position: number
  total: number
  loadWeight: number
  onPrevious: () => void
  onNext: () => void
  onExit: () => void
}

/** Shown while the camera is locked on one truck: step to the neighboring trucks or return to free view. */
export function LockBar({ truck, position, total, loadWeight, onPrevious, onNext, onExit }: LockBarProps) {
  return (
    <div className="center-lane lane-top">
      <div className="lock-bar glass" role="toolbar" aria-label="Truck view">
        <button className="icon-btn interactive" type="button" aria-label="Previous truck" title="Previous truck" onClick={onPrevious}><Icon name="chevronLeft" /></button>
        <div className="lock-info">
          <span className="lock-badge"><Icon name="lock" size={16} /></span>
          <span className="lock-text">
            <b>{truck.id}</b>
            <small>Truck {position} of {total}, {formatWhole(loadWeight)} of {formatWhole(truck.max_capacity)} kg</small>
          </span>
        </div>
        <button className="icon-btn interactive" type="button" aria-label="Next truck" title="Next truck" onClick={onNext}><Icon name="chevronRight" /></button>
        <span className="divider" aria-hidden="true" />
        <button className="icon-btn exit-btn" type="button" aria-label="Leave truck view" title="Leave truck view" onClick={onExit}><Icon name="close" /></button>
      </div>
    </div>
  )
}
