import type { ReactElement } from 'react'

const filled = { fill: 'currentColor', stroke: 'none' } as const
const shaded = { fill: 'currentColor', fillOpacity: 0.75, stroke: 'none' } as const
const CUBE_OUTLINE = 'M21 8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.7z'
const CUBE_EDGES = 'm3.3 7 8.7 5 8.7-5M12 22V12'

// Stroke paths follow the 24 px outline icon grid (adapted from Lucide, ISC license).
const ICONS = {
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  search: <><circle cx="11" cy="11" r="7.5" /><path d="m20.5 20.5-4-4" /></>,
  play: <path d="M7 4.5v15l12.5-7.5z" {...filled} />,
  pause: <><rect x="6" y="4.5" width="4" height="15" rx="1.2" {...filled} /><rect x="14" y="4.5" width="4" height="15" rx="1.2" {...filled} /></>,
  stepBack: <><path d="M18 5v14L8 12z" {...filled} /><path d="M6 5v14" /></>,
  stepForward: <><path d="M6 5v14l10-7z" {...filled} /><path d="M18 5v14" /></>,
  chevronLeft: <path d="m15 18-6-6 6-6" />,
  chevronRight: <path d="m9 18 6-6-6-6" />,
  close: <path d="M18 6 6 18M6 6l12 12" />,
  plus: <path d="M5 12h14M12 5v14" />,
  minus: <path d="M5 12h14" />,
  fit: <path d="M3 8V5a2 2 0 0 1 2-2h3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3" />,
  cube: <><path d={CUBE_OUTLINE} /><path d={CUBE_EDGES} /></>,
  // Camera angles as a view cube: the shaded face is the one the camera looks at.
  viewAngled: <><path d={CUBE_OUTLINE} /><path d={CUBE_EDGES} /></>,
  viewTop: <><path d="M12 2.7 20.4 7.3 12 12 3.6 7.3Z" {...shaded} /><path d={CUBE_OUTLINE} /><path d={CUBE_EDGES} /></>,
  viewFront: <><path d="M3.6 7.5 12 12.2v9.4l-8.4-4.8Z" {...shaded} /><path d={CUBE_OUTLINE} /><path d={CUBE_EDGES} /></>,
  layers: <><path d="M12.8 2.2a2 2 0 0 0-1.6 0L2.6 6.1a1 1 0 0 0 0 1.8l8.6 3.9a2 2 0 0 0 1.6 0l8.6-3.9a1 1 0 0 0 0-1.8z" /><path d="m22 12.7-9.2 4.1a2 2 0 0 1-1.6 0L2 12.7M22 17.7l-9.2 4.1a2 2 0 0 1-1.6 0L2 17.7" /></>,
  help: <><circle cx="12" cy="12" r="9.5" /><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01" /></>,
  history: <><path d="M3 12a9 9 0 1 0 9-9 9.7 9.7 0 0 0-6.7 2.7L3 8" /><path d="M3 3v5h5M12 7v5l4 2" /></>,
  panel: <><rect x="3" y="3" width="18" height="18" rx="3" /><path d="M15 3v18" /></>,
  lock: <><rect x="4" y="11" width="16" height="10" rx="2.5" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></>,
  truck: <><path d="M3 6h11v10H3zM14 9h4l3 3v4h-7" /><circle cx="7" cy="17.5" r="1.8" /><circle cx="17.5" cy="17.5" r="1.8" /></>,
  check: <path d="M20 6 9 17l-5-5" />,
  alert: <><circle cx="12" cy="12" r="9.5" /><path d="M12 7.5v5M12 16.2h.01" /></>,
  info: <><circle cx="12" cy="12" r="9.5" /><path d="M12 11v5.5M12 7.8h.01" /></>,
  expand: <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />,
  edit: <><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></>,
  dice: <><rect x="3" y="3" width="18" height="18" rx="4" /><circle cx="8.5" cy="8.5" r="1.2" {...filled} /><circle cx="15.5" cy="15.5" r="1.2" {...filled} /><circle cx="12" cy="12" r="1.2" {...filled} /></>,
  trash: <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" />,
  fragile: <path d="M8 3h8l-1 7a3 3 0 0 1-6 0zM12 13v7M8.5 21h7" />,
  upload: <path d="M12 15V3M7 8l5-5 5 5M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />,
  download: <path d="M12 3v12M7 10l5 5 5-5M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />,
  folder: <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />,
  refresh: <><path d="M21 12a9 9 0 0 1-15.5 6.3L3 16" /><path d="M3 12a9 9 0 0 1 15.5-6.3L21 8" /><path d="M21 3v5h-5M3 21v-5h5" /></>,
} satisfies Record<string, ReactElement>

export type IconName = keyof typeof ICONS

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONS[name]}
    </svg>
  )
}
