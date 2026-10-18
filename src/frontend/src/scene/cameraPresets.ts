import { Vector3 } from 'three'

/** Camera angles cycled by the view button, as directions from the framed center, with the icon that shows each. */
export const CAMERA_PRESETS = [
  { name: 'Angled view', icon: 'viewAngled', direction: new Vector3(0.55, 0.62, 1).normalize() },
  { name: 'Top view', icon: 'viewTop', direction: new Vector3(0, 1, 0.02).normalize() },
  { name: 'Front view', icon: 'viewFront', direction: new Vector3(0, 0.22, 1).normalize() },
] as const
