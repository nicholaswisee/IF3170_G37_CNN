import { Icon, type IconName } from '../ui/Icon'

interface MapControlsProps {
  onFit: () => void
  onZoomIn: () => void
  onZoomOut: () => void
  onNextView: () => void
  /** Current camera angle; the view button shows its icon. */
  view: { name: string; icon: IconName }
  nextViewName: string
}

/** Bottom right camera buttons, stacked like map controls. */
export function MapControls({ onFit, onZoomIn, onZoomOut, onNextView, view, nextViewName }: MapControlsProps) {
  return (
    <div className="map-controls">
      <div className="control-group glass">
        <button className="icon-btn interactive" type="button" aria-label="Fit view" title="Fit view" onClick={onFit}><Icon name="fit" /></button>
      </div>
      <div className="control-group glass">
        <button className="icon-btn interactive" type="button" aria-label="Zoom in" title="Zoom in" onClick={onZoomIn}><Icon name="plus" /></button>
        <span className="control-divider" aria-hidden="true" />
        <button className="icon-btn interactive" type="button" aria-label="Zoom out" title="Zoom out" onClick={onZoomOut}><Icon name="minus" /></button>
      </div>
      <div className="control-group glass">
        <button
          className="icon-btn interactive"
          type="button"
          aria-label={`${view.name}. Switch to ${nextViewName}`}
          title={`${view.name}. Click for ${nextViewName}`}
          onClick={onNextView}
        >
          <span key={view.icon} className="view-icon"><Icon name={view.icon} /></span>
        </button>
      </div>
    </div>
  )
}
