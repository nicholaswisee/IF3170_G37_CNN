import { useEffect, useRef, type ReactNode } from 'react'
import { Icon } from './Icon'

interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  headerExtra?: ReactNode
  size?: 'small' | 'large'
}

/** Glass sheet for views that need more room than a side panel. Escape is handled by the app shell. */
export function Modal({ title, onClose, children, footer, headerExtra, size = 'large' }: ModalProps) {
  const sheet = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    sheet.current?.querySelector<HTMLElement>('.sheet-body input, .sheet-body button, .sheet-foot button')?.focus()
    return () => previous?.focus()
  }, [])

  return (
    <div className="modal-root">
      <div className="scrim" onClick={onClose} />
      <div ref={sheet} className={size === 'small' ? 'sheet glass small' : 'sheet glass'} role="dialog" aria-modal="true" aria-label={title}>
        <div className="sheet-head">
          <h2>{title}</h2>
          {headerExtra}
          <button className="icon-btn" type="button" aria-label="Close" onClick={onClose}><Icon name="close" /></button>
        </div>
        <div className="sheet-body">{children}</div>
        {footer && <div className="sheet-foot">{footer}</div>}
      </div>
    </div>
  )
}
