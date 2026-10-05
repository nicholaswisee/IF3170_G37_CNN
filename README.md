# mejirowise

mejirowise is a project for IF3170 Artificial Intelligence, Assignment 1. It aims to optimize
package placement in trucks using Hill Climbing, Simulated Annealing, and a Genetic Algorithm,
with a browser interface for inspecting results in 3D.

The backend uses Python 3.12, FastAPI, Pydantic v2, and NumPy. The frontend uses React,
TypeScript, and Vite, with React Three Fiber / Three.js for visualization and Recharts for charts.

## Current status

The application scaffold, shared domain contract, and frontend contract fixtures are implemented.
The domain uses Pydantic `Problem`, `PackageSpec`, and `TruckSpec` models, six package orientations,
and placement-only search state. Package `value`/`weight` and truck `max_capacity` must be finite
(`allow_inf_nan=False`); frontend result validation also rejects non-finite metrics. Per-truck
occupancy and global state validation are implemented and tested for assignment consistency,
boundaries, overlap, capacity, support, and fragile packages.

Internal/public result scores and numeric event metrics must also be finite. Invalid requests return
422 with `detail` entries containing `type`, `loc`, and `msg`; raw input and exception context are
omitted so non-finite input cannot break error-response serialization.

Shared neighbor generation, both objective modes, and seeded feasible initialization are implemented.
Algorithms share an internal `SearchResult` and a typed `run` interface, with optional state
snapshots in history. Public request/result schemas and frontend history compatibility are aligned.
Sideways Hill Climbing is implemented and can be called directly through the algorithm interface.
Steepest-ascent, stochastic, and random-restart HC, Simulated Annealing, and Genetic Algorithm remain
unimplemented. The experiment runner, API algorithm dispatch, batch execution, persistence, and
algorithm-specific UI controls are pending. The scene renders a history snapshot when available and
otherwise `best_state`; the run endpoint still returns a placeholder and does not execute HC.
Frontend tests cover schema validation, placeholder API fixtures, and replay selection.

## Setup and run

### Docker (recommended)

Install Docker with the Docker Compose plugin, then run from the repository root:

```bash
docker compose up --build
```

Compose installs dependencies and starts both development servers. It mounts the source directories
for development, along with `data/` and `output/`. Startup uses service ordering only, not health
readiness waits; `/api/health` remains diagnostic. No database or separate environment file is required.

| Service                       | URL                                |
| ----------------------------- | ---------------------------------- |
| Frontend                      | <http://localhost:5173>            |
| Backend health check          | <http://localhost:8000/api/health> |
| Interactive API documentation | <http://localhost:8000/docs>       |

Stop the servers with `Ctrl+C`. To remove the stopped containers, run:

```bash
docker compose down
```

### Local development

Requirements: Python 3.12 with pip and venv, and Node.js 22.12+ (Node.js 20.19+ is also supported)
with npm. Run the backend and frontend in separate terminals.

Backend, starting from the repository root:

```bash
cd src/backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install ".[dev]"
OUTPUT_DIR=../../output DATA_DIR=../../data uvicorn app.main:app --reload --port 8000
```

On Windows, create the environment with `py -3.12 -m venv .venv` and activate it with
`.venv\Scripts\Activate.ps1` in PowerShell. Set `$env:OUTPUT_DIR = "../../output"` and
`$env:DATA_DIR = "../../data"`, then run `uvicorn app.main:app --reload --port 8000`.

Frontend, starting from the repository root:

```bash
cd src/frontend
npm ci
npm run dev -- --port 5173
```

Use the same URLs listed above. The frontend connects to `http://localhost:8000` by default.
Set `VITE_API_URL` before starting Vite if the backend runs elsewhere. The backend's
`FRONTEND_ORIGIN` setting controls the allowed browser origin and defaults to `http://localhost:5173`.

## Development checks

From `src/backend`, with the virtual environment activated:

```bash
ruff check .
ruff format --check .
mypy app
pytest
```

The tests cover occupancy, global constraints, objectives, seeded initialization/neighbors,
domain serialization/copy integration, schemas, placeholder API behavior, algorithm interface/result
contracts, and Sideways HC execution, seeded behavior, and termination. Other algorithms and real
algorithm execution through the API remain pending.

From `src/frontend`:

```bash
npm run build
npm run lint
npm test
```

## Team and planned responsibilities

These are the initial ownership areas. They describe planned work, not completed features.

| Student ID | Name                            | Main responsibilities                                                                  |
| ---------- | ------------------------------- | -------------------------------------------------------------------------------------- |
| 13524001   | Samuelson Dharmawan Tanuraharja | Hill Climbing, shared neighbor operations, and 3D visualization.                       |
| 13524037   | Nicholas Wise Saragih Sumbayak  | Shared domain models, Genetic Algorithm, and experiment results/statistics.            |
| 13524136   | Neswa Eka Anggara               | Simulated Annealing, constraint validation, objective evaluation, and API integration. |

All members contribute to integration and review of the shared interfaces.

## Repository structure

```text
src/backend/    FastAPI, domain models, validation, and optimization modules
src/frontend/   React application, API client, replay store, 3D scene, and charts
data/           Input data
output/         Reserved for experiment output
```

## Current API endpoints

- `GET /api/health`: checks backend availability.
- `GET /api/experiments`: returns an empty experiment list.
- `POST /api/experiments/run`: returns a deterministic placeholder result for the selected
  algorithm name. This endpoint does not run a search algorithm yet.
- `POST /api/problems/validate` and `POST /api/experiments/batch` are planned, not implemented.
