# mejirowise

Truck-loading optimization for IF3170 Artificial Intelligence, Assignment 1, with a 3D result viewer.
Backend: Python 3.12, FastAPI, Pydantic, and NumPy. Frontend: React, TypeScript, Vite,
Three.js (React Three F, Zustand, and Recharts.

## Current status

- Genetic Algorithm, Simulated Annealing, and Hill Climbing (steepest ascent, stochastic,
  sideways, and random restart) run through the API for single or multiple trucks.
- Batch execution supports the 18-run GA preset, per-configuration statistics, and JSON/CSV output.
  It is available through the API only; the UI has no batch screen.
- The UI provides controls for all three algorithms and the Hill Climbing variants, objective
  charts, result comparison, and manual snapshot replay (Previous/Next).
- Automatic replay is still pending: the Play/Pause buttons and playback speed selector exist,
  but nothing advances the iterations on a timer yet.

## Local development

Start commands from the repository root. Choose one setup; do not run both on the same ports.
The default setup does not require a database or `.env` file.

| Service                       | URL                                |
| ----------------------------- | ---------------------------------- |
| Frontend                      | <http://localhost:5173>            |
| Backend health check          | <http://localhost:8000/api/health> |
| Interactive API documentation | <http://localhost:8000/docs>       |

### With Docker

Install Docker Desktop, or Docker Engine with the Compose plugin. Make sure Docker is running.

First run:

```bash
docker compose up --build
```

Compose installs dependencies and starts both servers with reload enabled. Source, `data/`,
and `output/` are mounted from the host; Python and Node.js are not required on the host.

Subsequent runs:

```bash
docker compose up
```

Stop with `Ctrl+C`, then remove the containers with `docker compose down`. Saved results remain
in the host's `output/` directory.

After changing dependencies, rebuild and refresh the frontend dependency volume:

```bash
docker compose up --build --renew-anon-volumes
```

### Without Docker

Requirements: Python **3.12** with `venv` and pip, plus Node.js **22.12+** (or **20.19+**) with npm.
Python 3.13+ is not supported by the backend configuration.

#### One-time setup

Linux/macOS:

```bash
python3.12 -m venv src/backend/.venv
src/backend/.venv/bin/python -m pip install -e "./src/backend[dev]"
npm --prefix src/frontend ci
```

Windows PowerShell:

```powershell
py -3.12 -m venv src/backend/.venv
.\src\backend\.venv\Scripts\python.exe -m pip install -e "./src/backend[dev]"
npm --prefix src/frontend ci
```

Keep the venv for later sessions. Repeat the install commands when `pyproject.toml` or
`package-lock.json` changes.

#### Terminal 1: backend

Linux/macOS:

```bash
cd src/backend
OUTPUT_DIR=../../output DATA_DIR=../../data .venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Windows PowerShell:

```powershell
cd src/backend
$env:OUTPUT_DIR = "../../output"
$env:DATA_DIR = "../../data"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The directory variables replace Docker's `/workspace/...` defaults. Commands use the venv's
interpreter directly, so activation is optional.

#### Terminal 2: frontend

Open a new terminal at the repository root:

```bash
cd src/frontend
npm run dev -- --port 5173 --strictPort
```

Open <http://localhost:5173> once both servers are running. Stop each with `Ctrl+C`.
`--strictPort` reports an occupied port instead of silently switching to another one.

For different local addresses, set `VITE_API_URL` when starting Vite and `FRONTEND_ORIGIN` when
starting Uvicorn. With Docker, change the corresponding environment values and port mappings
in `docker-compose.yml`.

## Development checks

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

## API and saved results

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| GET | `/api/health` | Backend status |
| POST | `/api/problems/validate` | Validate a problem definition |
| GET | `/api/experiments` | Saved individual results |
| POST | `/api/experiments/run` | Run GA, Simulated Annealing, or Hill Climbing (any variant) |
| GET | `/api/experiments/presets/genetic_algorithm` | List the 18 GA preset specifications |
| POST | `/api/experiments/batch` | Execute explicit runs or the `ga_mandatory` preset |

Use `/docs` to inspect request bodies. `persist` defaults to `true` for direct API calls, which
saves individual results under `output/experiments/` and batch JSON/CSV under `output/batches/`;
send `persist: false` to skip saving. UI runs send `persist: false` and remain available only
during the current page session.

## Deployment

The backend runs on Render's free plan and the frontend on Cloudflare Pages, both from this
repository.

Backend (Render): create a Blueprint from this repository. `render.yaml` builds
`src/backend/Dockerfile` without dev dependencies or reload. Set `FRONTEND_ORIGIN` to the
deployed frontend URL without a trailing slash. Free services sleep after 15 idle minutes and
take about a minute to wake. Saved results under `OUTPUT_DIR` are lost on restart.

Frontend (Cloudflare Pages): connect this repository with root directory `src/frontend`, build
command `npm run build`, and output directory `dist`. Set the build variables
`VITE_API_URL=https://<backend>.onrender.com` and `NODE_VERSION=22`. `VITE_API_URL` is embedded
at build time, so redeploy the frontend after changing it.

## Team

| Student ID | Name                            | Main responsibilities                                                                  |
| ---------- | ------------------------------- | -------------------------------------------------------------------------------------- |
| 13524001   | Samuelson Dharmawan Tanuraharja | Hill Climbing, shared neighbor operations, and 3D visualization.                       |
| 13524037   | Nicholas Wise Saragih Sumbayak  | Shared domain models, Genetic Algorithm, and experiment results/statistics.            |
| 13524136   | Neswa Eka Anggara               | Simulated Annealing, constraint validation, objective evaluation, and API integration. |

## Repository structure

```text
src/backend/    FastAPI, domain models, validation, and optimization modules
src/frontend/   React application, API client, replay store, 3D scene, and charts
data/           Reserved for input data (currently empty; not read by the code)
output/         Saved experiment JSON and batch JSON/CSV
docs/           Report (LaTeX source and PDF), slides, and figures
```
