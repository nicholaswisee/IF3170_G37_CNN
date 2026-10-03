# mejirowise

mejirowise is a project for IF3170 Artificial Intelligence, Assignment 1. It aims to optimize
package placement in trucks using Hill Climbing, Simulated Annealing, and a Genetic Algorithm,
with a browser interface for inspecting results in 3D.

The backend uses Python 3.12, FastAPI, Pydantic v2, and NumPy. The frontend uses React,
TypeScript, and Vite, with React Three Fiber / Three.js for visualization and Recharts for charts.

## Current status

The application scaffold and shared domain contract are implemented. The domain includes immutable
package and truck specifications, fleet problems, six package orientations, and placement-only
search state. Per-truck occupancy and global state validation are implemented and tested for
assignment consistency, boundaries, overlap, capacity, support, and fragile packages.

Neighbor generation, search algorithms, objective evaluation, random initialization, and experiment
execution remain unimplemented. The current scene uses preview data, and the experiment API returns
placeholder results rather than optimized placements.

## Setup and run

### Docker (recommended)

Install Docker with the Docker Compose plugin, then run from the repository root:

```bash
docker compose up --build
```

Compose installs dependencies and starts both development servers. It mounts the source directories
for development, along with `data/` and `output/`. No database or separate environment file is required
for the default setup.

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

The tests cover occupancy, global constraints, and domain serialization/copy integration.
They do not yet cover execution of the pending search algorithms or experiment API integration.

From `src/frontend`:

```bash
npm run build
npm run lint
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
src/backend/    FastAPI, domain models, occupancy/validator, and optimization scaffolds
src/frontend/   React application, API client, replay store, 3D scene, and charts
data/           Input data
docs/           Project specifications and task planning
output/         Reserved for experiment output
```

## Current API endpoints

- `GET /api/health`: checks backend availability.
- `GET /api/experiments`: returns an empty experiment list.
- `POST /api/experiments/run`: returns a deterministic placeholder result for the selected
  algorithm name. This endpoint does not run a search algorithm yet.
