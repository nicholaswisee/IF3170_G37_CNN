# IF3170 Tugas Besar 1 — Container Optimization Visualizer

This repository contains the initial development scaffold for the IF3170 Tugas Besar 1 project.
The Python backend owns the future optimization engine and exposes a FastAPI contract. The React
frontend consumes that contract and renders the container state with Three.js through React Three
Fiber.

## Architecture

```text
Browser
  │
  ▼
React + Vite + TypeScript
React Three Fiber / Three.js
  │ HTTP / JSON
  ▼
FastAPI backend
  │
  ▼
Future Python optimization core
```

The optimization core remains independent from the frontend. The current algorithm and experiment
modules are intentionally stubs; React only visualizes backend data.

## Requirements

Docker and Docker Compose are the recommended development environment. Local development can also
use Python 3.12 and Node.js LTS.

## Quick start

```bash
docker compose up --build
```

Open:

- Frontend: <http://localhost:5173>
- Backend: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>

## Development commands

From `src/backend`:

```bash
ruff check .
ruff format --check .
mypy app
```

From `src/frontend`:

```bash
npm run dev
npm run build
npm run lint
```

## Repository structure

```text
src/backend/    FastAPI app, domain contracts, and future optimization boundaries
src/frontend/   React/Vite UI, API client, replay store, 3D scene, and chart
data/           Local input data mount
docs/           Project documentation
output/         Generated experiment output mount
```

## API scaffold

- `GET /api/health` reports backend availability.
- `GET /api/experiments` returns an empty experiment list.
- `POST /api/experiments/run` returns a deterministic placeholder result for the three planned
  algorithm names.

## Status

Current milestone: project scaffolding only. Hill Climbing, Simulated Annealing, Genetic Algorithm,
objective evaluation, constraints, neighbor generation, experiment execution, and replay generation
are not implemented yet.
