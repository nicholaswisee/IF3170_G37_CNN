import type { TruckSpec } from '../../types/experiment'

interface TruckSelectorProps {
  trucks: TruckSpec[]
  selectedTruckId: string
  onSelect: (truckId: string) => void
}

export function TruckSelector({ trucks, selectedTruckId, onSelect }: TruckSelectorProps) {
  return (
    <div className="truck-selector" role="group" aria-label="Select truck">
      {trucks.map((truck) => (
        <button
          key={truck.id}
          type="button"
          aria-pressed={truck.id === selectedTruckId}
          onClick={() => onSelect(truck.id)}
        >
          {truck.id}
        </button>
      ))}
    </div>
  )
}
