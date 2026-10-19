import { Modal } from '../ui/Modal'

/** Each control is either a pointer gesture or one or more keyboard keys. */
const CONTROLS: { action: string; gesture?: string; keys?: string[] }[] = [
  { action: 'Locks the camera on a truck', gesture: 'Click a truck' },
  { action: 'Orbits the camera, or only that truck when locked', gesture: 'Drag' },
  { action: 'Pans across the fleet in free view', gesture: 'Right drag' },
  { action: 'Zooms in and out', gesture: 'Scroll' },
  { action: 'Moves the lock to the previous or next truck', keys: ['[', ']'] },
  { action: 'Leaves truck view or closes a window', keys: ['Esc'] },
  { action: 'Plays or pauses the replay', keys: ['Space'] },
  { action: 'Steps back or forward', keys: ['←', '→'] },
  { action: 'Fits the camera to the view', keys: ['F'] },
]

export function HelpSheet({ onClose }: { onClose: () => void }) {
  return (
    <Modal title="Controls and shortcuts" onClose={onClose} size="small">
      <div className="group">
        {CONTROLS.map(({ action, gesture, keys }) => (
          <div className="row" key={action}>
            <span className="row-label"><span>{action}</span></span>
            <span className="keys">{gesture ?? keys?.map((key) => <kbd key={key}>{key}</kbd>)}</span>
          </div>
        ))}
      </div>
      <p className="caption">Packages that change trucks fly over the walls, and the move trail shows their path for the current step.</p>
    </Modal>
  )
}
