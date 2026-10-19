# mejirowise

Truck-loading optimization for IF3170 Artificial Intelligence, with a 3D result viewer.

<div align="center">
  <h3>Tech Stacks</h3>

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)](https://numpy.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vite.dev/)
[![Three.js](https://img.shields.io/badge/Three.js-000000?style=for-the-badge&logo=threedotjs&logoColor=white)](https://threejs.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

</div>

## Project structure

```text
.
├── src/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/            HTTP routes, request limits, and error responses
│   │   │   ├── domain/         Package, truck, problem, state, and move models
│   │   │   ├── experiments/    Run execution, presets, metrics, and result recording
│   │   │   ├── optimization/   Constraints, initialization, neighbors, and scoring
│   │   │   │   └── algorithms/ Optimization algorithm implementations
│   │   │   └── schemas/        API request and response validation
│   │   └── tests/              Backend tests and contract fixtures
│   └── frontend/
│       └── src/
│           ├── api/            Backend client, requests, and validation
│           ├── charts/         Experiment charts and chart data
│           ├── copy/           Display text formatting
│           ├── mocks/          Sample fleet data
│           ├── modals/         Help, problem editor, and saved-run dialogs
│           ├── panels/         Setup and results panels
│           ├── scene/          3D trucks, packages, camera, and scene labels
│           ├── shell/          Navigation, playback, and viewer controls
│           ├── stores/         Shared replay state
│           ├── styles/         Stylesheets and design tokens
│           ├── testing/        Shared test fixtures
│           ├── types/          Shared TypeScript types
│           ├── ui/             Reusable interface components
│           └── viewer/         Geometry, result normalization, and scene models
├── data/                       Input data
└── output/                     Saved experiment JSON and batch JSON/CSV
```

## Local development

Choose Docker or a local setup below. Start from the repository root.
Open <http://localhost:5173> when both servers are running. Stop with `Ctrl+C`.

### With Docker

Install and start Docker Desktop (or Docker Engine with the Compose plugin), then run:

```bash
docker compose up --build
```

This starts both servers with live reload. No local Python or Node.js installation is needed.
Use `docker compose up` for later runs, or the following after dependency changes:

```bash
docker compose up --build --renew-anon-volumes
```

Remove containers with `docker compose down`. Saved results stay in `output/`.

### Without Docker

Install Python **3.12** (with `venv` and pip) and Node.js **22.12+** (or **20.19+**) with npm.

#### macOS / Linux

**Terminal 1 — backend:**

```bash
cd src/backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — frontend** (from the repository root):

```bash
cd src/frontend
npm ci
npm run dev -- --port 5173 --strictPort
```

#### Windows (PowerShell)

**Terminal 1 — backend:**

```powershell
cd src/backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — frontend** (from the repository root):

```powershell
cd src/frontend
npm ci
npm run dev -- --port 5173 --strictPort
```

For later runs, skip venv creation and dependency installation unless dependencies changed.
If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` instead of `python`
and skip the activation command.

## Dev Checks

Without Docker, from `src/backend` (use `.\.venv\Scripts\python.exe` on Windows):

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy app
```

From `src/frontend`:

```bash
npm test
npm run build
npm run lint
```

With Docker running, from the repository root:

```bash
docker compose exec backend python -m pytest
docker compose exec frontend npm test
```

## Team

| Student ID | Name                            | Main responsibilities                                                                  |
| ---------- | ------------------------------- | -------------------------------------------------------------------------------------- |
| 13524001   | Samuelson Dharmawan Tanuraharja | Hill Climbing, shared neighbor operations, and 3D visualization.                       |
| 13524037   | Nicholas Wise Saragih Sumbayak  | Shared domain models, Genetic Algorithm, and experiment results/statistics.            |
| 13524136   | Neswa Eka Anggara               | Simulated Annealing, constraint validation, objective evaluation, and API integration. |
