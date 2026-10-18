import { ORIENTATION_NAMES, formatNumber, placementText } from '../copy/format'
import type { OptimizationState, Problem } from '../types/experiment'
import { Icon } from '../ui/Icon'
import { getOrientedDimensions } from '../viewer/geometry'
import { packageColor, type ColorMode } from '../viewer/sceneModel'

interface PackageCardProps {
  problem: Problem
  state: OptimizationState
  packageId: string
  colorMode: ColorMode
  onClose: () => void
}

/** Floating details card for the package picked in the scene, the search, or the Outside list. */
export function PackageCard({ problem, state, packageId, colorMode, onClose }: PackageCardProps) {
  const index = problem.packages.findIndex((pkg) => pkg.id === packageId)
  const pkg = problem.packages[index]
  if (!pkg) return null
  const placement = state.placements.find((item) => item.package_id === packageId)
    ?? { package_id: packageId, truck_id: null, position: null, orientation: 0 as const }
  const [w, l, h] = getOrientedDimensions(pkg, placement.orientation)
  const rows: [string, string][] = [
    ['Location', placementText(placement)],
    ['Size', `${pkg.width} × ${pkg.length} × ${pkg.height}`],
    ['Placed as', `${w} × ${l} × ${h} (${ORIENTATION_NAMES[placement.orientation]})`],
    ['Value', formatNumber(pkg.value)],
    ['Weight', `${formatNumber(pkg.weight)} kg`],
    ['ETA', String(pkg.eta)],
  ]
  return (
    <section className="package-card glass" aria-label={`Package ${pkg.id}`}>
      <div className="package-card-head">
        <span className="swatch" style={{ background: packageColor(problem, index, colorMode) }} aria-hidden="true" />
        <h3>{pkg.id}</h3>
        {pkg.is_fragile && <span className="tag red">Fragile</span>}
        <button className="icon-btn" type="button" aria-label="Close package details" onClick={onClose}><Icon name="close" size={18} /></button>
      </div>
      <div className="group">
        {rows.map(([label, value]) => (
          <div className="row" key={label}>
            <span className="row-label"><span>{label}</span></span>
            <span className="row-value">{value}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
