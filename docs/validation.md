# Occupancy and global validator

These shared functions implement the occupancy and validation contracts from sections 11–15
of the team's Architecture Freeze. They are available in
`app.optimization.constraints` for the initializer, neighbor engine, algorithms, GA repair,
and API integration.

## Inputs and results

Use the existing Pydantic domain classes from `app.domain`. One `Problem` contains all
packages and at least one truck. One `State` contains exactly one placement for every
package ID, with no duplicate or unknown package IDs. Placement order is irrelevant.

A loaded placement has both `truck_id` and `position`; an outside placement has both set
to `None`. Orientation belongs to the placement. Coordinates are integer anchors with
`x=width`, `y=length`, and `z=height`.

```python
from app.domain import Problem, State
from app.optimization.constraints import build_occupancies, validate_state

# problem_json and state_json are complete serialized domain models.
problem = Problem.model_validate_json(problem_json)
state = State.model_validate_json(state_json)
result = validate_state(problem, state)

if result.valid:
    occupancies = build_occupancies(problem, state)
else:
    print(result.errors)
```

Malformed domain input can raise Pydantic `ValidationError` during parsing. Once parsed,
`validate_state(problem, state)` returns a `ValidationResult` with:

- `valid`: whether the complete state satisfies all constraints;
- `errors`: human-readable constraint failures in the frozen validation order;
- `truck_weights`: loaded weight keyed by truck ID, including zero for empty trucks.

For invalid states, weight totals include only unique known packages with consistent
assignments to known trucks. Packages with invalid geometry still contribute weight;
ambiguous duplicate assignments are excluded. Errors are not necessarily exhaustive:
geometric checks exclude structurally invalid placements, support checks are skipped
when assignments are structurally invalid, and support checks are skipped for trucks whose
boundary or overlap errors prevent an unambiguous occupancy grid.

## Validation order and semantics

1. Every package has exactly one known placement.
2. Truck and position are either both assigned or both absent.
3. Assigned truck IDs exist.
4. Oriented package dimensions fit entirely within the assigned truck.
5. Packages do not overlap within the same truck.
6. Each truck's loaded weight is at most its own capacity.
7. A package is on the floor or has at least one occupied cell directly below its base.
8. No base contact is supported by a fragile package.

Partial support is valid. A fragile package can stand on the floor or a non-fragile
package, but cannot support another package. Support and capacity are independent
between trucks. All placements are checked on every call, so moving a support package
can invalidate a package that did not itself move.

## Occupancy is derived

`build_occupancies(problem, state)` returns `dict[str, np.ndarray]`. Each truck's grid
has shape `(width, length, height)` and dtype `np.int32`. Empty cells contain `-1`;
occupied cells contain the package's index in `problem.packages`. Outside packages
occupy no cells. Returned arrays are newly allocated, and inputs are not modified.

The builder raises `ValueError` for structural, boundary, or overlap errors. It does not
check capacity, support, or fragile rules: a floating package still has representable
geometry. Call `validate_state` to decide whether a candidate is feasible. Both public
functions share the same internal assignment and geometry checks.

Use `state.model_copy(deep=True)` before editing a search candidate and validate the
complete candidate afterward. Use Pydantic's `model_dump_json()` and
`model_validate_json()` for serialization. Keep occupancy, validity, and weight totals
outside canonical `State`.

## Verification and integration status

From `src/backend`, with Python 3.12 and the project's development dependencies installed:

```bash
ruff check .
ruff format --check .
mypy app
pytest
```

Targeted domain–occupancy–validator integration checks:

```bash
pytest -q tests/test_validation_integration.py
```

These checks cover JSON round trips with numeric orientations and outside packages,
multiple trucks, copied candidates, cross-truck support removal, and consistent rejection
of invalid geometry. Unit tests cover the remaining individual occupancy/constraint cases.

The occupancy and validator work is ready for the next shared-core integration step.
Neighbor generation, objective evaluation, random initialization, and search/API execution
still require implementation. Passing these tests does not complete the team's full
Core Merge Gate or Freeze Merge Gate 0.
