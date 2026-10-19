import type { PackageSpec, Problem, TruckSpec } from '../types/experiment'

export type TruckDraft = { [Field in keyof TruckSpec]: string }
export type PackageDraft = { [Field in Exclude<keyof PackageSpec, 'is_fragile'>]: string } & { is_fragile: boolean }

interface DraftRow<Values> {
  key: number
  values: Values
}

export interface ProblemFormState {
  trucks: DraftRow<TruckDraft>[]
  packages: DraftRow<PackageDraft>[]
  nextKey: number
}

export type ProblemFormAction =
  | { type: 'add-truck' }
  | { type: 'add-package' }
  | { type: 'remove-truck' | 'remove-package'; key: number }
  | { type: 'update-truck'; key: number; changes: Partial<TruckDraft> }
  | { type: 'update-package'; key: number; changes: Partial<PackageDraft> }

export function createProblemForm(problem: Problem): ProblemFormState {
  return {
    trucks: problem.trucks.map((truck, key) => ({ key, values: {
      id: truck.id, width: String(truck.width), length: String(truck.length),
      height: String(truck.height), max_capacity: String(truck.max_capacity),
    } })),
    packages: problem.packages.map((pkg, index) => ({ key: problem.trucks.length + index, values: {
      id: pkg.id, width: String(pkg.width), length: String(pkg.length), height: String(pkg.height),
      value: String(pkg.value), weight: String(pkg.weight), eta: String(pkg.eta), is_fragile: pkg.is_fragile,
    } })),
    nextKey: problem.trucks.length + problem.packages.length,
  }
}

function nextId(prefix: string, rows: DraftRow<{ id: string }>[]): string {
  const ids = new Set(rows.map((row) => row.values.id.trim()))
  let index = 1
  while (ids.has(`${prefix}-${index}`)) index += 1
  return `${prefix}-${index}`
}

export function problemFormReducer(state: ProblemFormState, action: ProblemFormAction): ProblemFormState {
  switch (action.type) {
    case 'add-truck':
      return { ...state, nextKey: state.nextKey + 1, trucks: [...state.trucks, {
        key: state.nextKey,
        values: { id: nextId('truck', state.trucks), width: '1', length: '1', height: '1', max_capacity: '0' },
      }] }
    case 'add-package':
      return { ...state, nextKey: state.nextKey + 1, packages: [...state.packages, {
        key: state.nextKey,
        values: { id: nextId('package', state.packages), width: '1', length: '1', height: '1', value: '0', weight: '0', eta: '0', is_fragile: false },
      }] }
    case 'remove-truck':
      return state.trucks.length <= 1 ? state : { ...state, trucks: state.trucks.filter((row) => row.key !== action.key) }
    case 'remove-package':
      return { ...state, packages: state.packages.filter((row) => row.key !== action.key) }
    case 'update-truck':
      return { ...state, trucks: state.trucks.map((row) => row.key === action.key ? { ...row, values: { ...row.values, ...action.changes } } : row) }
    case 'update-package':
      return { ...state, packages: state.packages.map((row) => row.key === action.key ? { ...row, values: { ...row.values, ...action.changes } } : row) }
  }
}

export type ProblemFormErrors = Record<string, string>

export type ProblemFormResult =
  | { problem: Problem; errors: ProblemFormErrors }
  | { problem: null; errors: ProblemFormErrors }

export function parseProblemForm(state: ProblemFormState): ProblemFormResult {
  const errors: ProblemFormErrors = {}
  if (state.trucks.length === 0) errors.trucks = 'At least one truck is required.'

  function validateIds(collection: 'trucks' | 'packages') {
    const firstPaths = new Map<string, string>()
    for (const row of state[collection]) {
      const id = row.values.id.trim()
      const path = `${collection}.${row.key}.id`
      if (id === '') errors[path] = 'ID is required.'
      else {
        const first = firstPaths.get(id)
        if (first !== undefined) {
          errors[first] = errors[path] = 'IDs must be unique within this list.'
        } else firstPaths.set(id, path)
      }
    }
  }

  function numeric(value: string, path: string, minimum: number, integer: boolean): number {
    const number = Number(value)
    if (value.trim() === '') errors[path] = 'This field is required.'
    else if (!Number.isFinite(number)) errors[path] = 'Enter a finite number.'
    else if (integer && !Number.isSafeInteger(number)) errors[path] = 'Enter a whole number within the safe integer range.'
    else if (number < minimum) errors[path] = minimum === 1 ? 'Enter a positive number.' : 'Enter zero or a positive number.'
    return number
  }

  function dimensions(values: TruckDraft | PackageDraft, path: string) {
    return {
      width: numeric(values.width, `${path}.width`, 1, true),
      length: numeric(values.length, `${path}.length`, 1, true),
      height: numeric(values.height, `${path}.height`, 1, true),
    }
  }

  validateIds('trucks')
  validateIds('packages')
  const trucks = state.trucks.map(({ key, values }) => ({
    id: values.id.trim(),
    ...dimensions(values, `trucks.${key}`),
    max_capacity: numeric(values.max_capacity, `trucks.${key}.max_capacity`, 0, false),
  }))
  const packages = state.packages.map(({ key, values }) => ({
    id: values.id.trim(),
    ...dimensions(values, `packages.${key}`),
    value: numeric(values.value, `packages.${key}.value`, 0, false),
    weight: numeric(values.weight, `packages.${key}.weight`, 0, false),
    eta: numeric(values.eta, `packages.${key}.eta`, 0, true),
    is_fragile: values.is_fragile,
  }))
  return { problem: Object.keys(errors).length === 0 ? { trucks, packages } : null, errors }
}
