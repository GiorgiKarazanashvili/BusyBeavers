# Cohort Control Tower dashboard (`frontend/`)

The Streamlit dashboard of the Busy Beavers Cohort Control Tower. It is a pure client of the FastAPI backend in
`backend/`: it lists releases, starts a comparison, shows what the detection engine (`detection/engine.py`)
found, and downloads the validated `findings.json`. It performs no detection, analysis or repair logic itself.

| File | Role |
|---|---|
| `frontend/app.py` | the dashboard (single Streamlit script) |
| `frontend/api_client.py` | the HTTP client the dashboard uses (`ApiClient`) |
| `frontend/local_backend.py` | sidecar launcher: starts `uvicorn backend.main:app` next to the dashboard when no API answers, and fetches the official data on first start (used on Streamlit Community Cloud) |
| `frontend/requirements.txt` | what Streamlit Community Cloud installs (dashboard + backend + validator + engine dependencies) |
| `.streamlit/config.toml` (repo root) | Streamlit base theme (dark, warm brown), no sidebar, minimal toolbar |

## Run it

The API must be running first. Both commands are run from the repository root with the virtual environment
active.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --port 8000          # terminal 1
```
```powershell
.\.venv\Scripts\Activate.ps1
streamlit run frontend\app.py                 # terminal 2 -> http://localhost:8501
```

Linux / macOS:

```bash
source .venv/bin/activate
uvicorn backend.main:app --port 8000          # terminal 1
```
```bash
source .venv/bin/activate
streamlit run frontend/app.py                 # terminal 2 -> http://localhost:8501
```

Requirements: Python 3.11+, `streamlit>=1.45`, `requests`, `pandas` (all in `requirements.txt`). Start Streamlit
from the repository root so it picks up `.streamlit/config.toml`.

## Deploy as a website (Streamlit Community Cloud)

The repository runs as a public website on [share.streamlit.io](https://share.streamlit.io) with **both** the
repository's backend and frontend: Community Cloud runs one command (`streamlit run frontend/app.py`), so on
start the dashboard checks `CCT_API_URL` and, when nothing answers, launches the repository's own
`uvicorn backend.main:app` on `127.0.0.1:8000` as a child process and then talks to it over HTTP exactly as it does
locally. No request bypasses the API, and `backend/` and `detection/` are untouched. On the very first start it also
downloads the official baseline (5 files, no RNA, checksum-verified by `data/tcga-brca/fetch.py --no-rna`) and
builds `practice-B` with `data/tcga-brca/make_release.py`, because raw data is not in the repository.

Settings: main file `frontend/app.py`; Python 3.12; Community Cloud installs `frontend/requirements.txt`
(uvicorn included). `CCT_MODE` (environment variable or Streamlit secret) selects the behaviour:

| `CCT_MODE` | Behaviour |
|---|---|
| `auto` (default) | connect to `CCT_API_URL`; start the sidecar if nothing answers |
| `http` | only connect (the classic two-terminal setup) |
| `sidecar` | always make sure the sidecar runs at `CCT_API_URL` |

The top-bar status reads `API (sidecar) v… · engine: auto-discovered` when the dashboard started the backend
itself. Runs and uploads live in the container's `outputs/` and disappear when Community Cloud restarts the app
(after inactivity or a new commit); a fresh start re-downloads the data in a few seconds. Step-by-step deployment
instructions are in `DEPLOY_STREAMLIT_CLOUD.md` of the delivery.

## What you see

**Top bar**: project name, `Home | Runs | Engine | Mission`, the **Dark / Light** switch and the API/engine status
(`engine: auto-discovered` means `detection/engine.py` was found; `MOCK` means `CCT_DETECTOR=mock` is set on the API;
`not configured` means the API found no engine and Compare is disabled).

**Home** has two panels side by side.

The work panel (left) has four tabs:

| Tab | Contents |
|---|---|
| **Select release** | Release A and B pickers, file availability and metadata for the chosen releases, **Compare releases**. On the right: the current run with live progress, the previous-runs picker and an upload box (five files or one .zip) |
| **Results** | verdict card, validation line, human-intervention line, metric cards (samples per release, patients, ids added/removed, ids changed in at least one file, swaps, duplicates, findings), the findings table with filters (severity, type, confidence, affected analysis, review-only, search), one finding opened with its evidence pointers, impact reasons, limitation and linked repairs, **Download findings.json** |
| **Next steps** | every proposed repair with its targets, handling and reviewer decision (if a Repair Review Desk added one), the reviewer-decisions table, and the analysis impact (A1/A2 status, rerun or not and why, what each analysis reads, before/after with a Δ column) |
| **Detailed info** | releases on the server, sample-id counts per file, run metadata and engine notes; SHA-256 per file per release, dataset and producer, engine blocks, progress log, raw `findings.json`, download |

The quick-summary panel (right): face cards (verdict, human intervention required, findings, risk tier), the
automatic-fix candidates, a workflow checklist (data, engine, run, validator, review, download; review and download
are never ticked by the tool) and recent runs.

**Runs** lists all runs and opens one on Home. **Engine** explains how the API finds the detection engine and
shows the server checks. **Mission** restates the product brief.

## Themes

Dark (default) uses the warm brown palette from `.streamlit/config.toml`; Light is a muted tan. The switch in the
top bar restyles everything, including tables, inputs, buttons and notices, without reloading. The choice lives in the
browser session. If the browser's Streamlit theme setting is Light the dashboard starts in Light.

## API calls

| Call | Used for |
|---|---|
| `GET /api/health` | top-bar status, engine status, Engine page (cached 5 s) |
| `GET /api/releases` | release pickers, availability and metadata tables |
| `POST /api/releases/upload` | the upload box |
| `POST /api/compare` `{"release_a","release_b"}` | **Compare releases** (asynchronous; the dashboard polls) |
| `GET /api/runs` | previous runs, Runs page, recent runs |
| `GET /api/runs/{run_id}` | status, progress, summary metrics, validation |
| `GET /api/runs/{run_id}/findings` | the validated `findings.json` (shown and downloaded byte-for-byte) |
| `GET /api/runs/{run_id}/triage` | optional: risk tier and automatic-fix candidates |

**Without `/triage`** (the current backend): the quick summary is built from `findings.json` itself (verdict,
findings count, human-intervention flag from `needs_human_review` and the presence of repairs), the risk-tier card
reads "not available", the Automatic fixes block explains why, and every repair is listed under Next steps as
"review (no triage endpoint)". Nothing else changes. If the endpoint is added later (see
`optional-backend-triage/README.md` in the delivery zip), the dashboard uses it automatically.

## Configuration

| Setting | Where | Default |
|---|---|---|
| API address | environment variable `CCT_API_URL`, or the API URL field on the Engine page | `http://127.0.0.1:8000` |
| Theme at start | browser Streamlit theme, then the top-bar switch | dark |
| Streamlit port | `streamlit run frontend/app.py --server.port 8502` | 8501 |

Example, PowerShell: `$env:CCT_API_URL = "http://127.0.0.1:8010"; streamlit run frontend\app.py`

## How the engine's output appears

The dashboard shows whatever the backend packaged from `detection/engine.py` into `findings.json` (format v0.2):

- `findings[]`: table and detail view. `kind`, `severity`, `confidence`, `summary`, `evidence[]`, `affects_analyses`,
  `not_affected_analyses`, `limitation`, `needs_human_review` are used directly. Optional extras are shown when
  present: `file` (otherwise taken from the evidence pointers), `impact_reasons` (`{"A1": "...", "A2": "..."}`),
  `details` (any dict, under "Engine details").
- `analyses[]`: `id`, `status` (`changed` / `unchanged` / `not_rerun`), `before`, `after`, and the optional `title`,
  `inputs`, `reads`, `triggered_by`, `reason`, `comparison`, `after_excluding_flagged`. Nested dicts in
  `before`/`after` (for example A2 counts per subtype) become one row each.
- `repairs[]`: `id`, `action`, `targets[]`, `justification`, `addresses[]`.
- `decisions[]` (from a Repair Review Desk): shown per repair and in the reviewer-decisions table.
- `verdict`: the verdict card; an unknown value is shown as "No verdict from the engine".

Summary cards (samples, patients, ids added/removed, changed in ≥1 file) come from the backend's file inventory;
finding counts are tallied from the engine's findings by `kind` and evidence pointers.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Backend not available" panel | locally: start `uvicorn backend.main:app --port 8000` from the repository root, or set the API URL on the Engine page / `CCT_API_URL`. On Community Cloud: open the "Startup log" expander and the app logs (Manage app); usually a missing package in `frontend/requirements.txt` |
| Compare is disabled, status `engine: not configured` | the API found no engine: make sure `detection/engine.py` exists in the repo root or set `CCT_DETECTOR` for the API process, then restart uvicorn |
| Port 8501 or 8000 already in use | `streamlit run frontend\app.py --server.port 8502` / `uvicorn backend.main:app --port 8010` and set `CCT_API_URL` accordingly. On Windows, find the holder with `netstat -ano \| findstr :8501` and stop it with `Stop-Process -Id <pid>` |
| Old look, tiny tabs, light boxes on dark | hard-refresh the browser (Ctrl+F5), make sure Streamlit was started from the repo root (so `.streamlit/config.toml` applies) and that `streamlit --version` is 1.45 or newer (`pip install -U streamlit`) |
| `TypeError: ... unexpected keyword argument 'key'` or `'width'` | Streamlit too old: `pip install -U "streamlit>=1.45"` |
| Windows SmartScreen / Application Control blocks `streamlit.exe` | run it through Python instead: `python -m streamlit run frontend\app.py` (same for uvicorn: `python -m uvicorn backend.main:app --port 8000`) |
| Run stays "running" for minutes | the engine is still working on large files; the page polls every 1.5 s. If uvicorn was restarted mid-run the run is marked failed and a new Compare is needed |
| Quick summary shows "Risk tier: not available" | expected without the optional `/triage` endpoint |
| Upload rejected | only the five release files (optionally `rna_hiseq.tsv.gz`) or one .zip containing them; 200 MB per file; names must be the official file names |

## Development notes

- Run the headless dashboard checks in the main project with `pytest -q tests/test_frontend.py` (they start a mock
  API and drive the page with `streamlit.testing.v1.AppTest`).
- Styling is in the `CSS` string at the top of `app.py`; colours are the `THEMES` dict (two palettes → CSS variables).
  Containers are keyed (`topbar`, `panel1`, `panel2`, `subpanel-*`) so CSS can target them; tables are rendered as HTML
  by `table()` so they take the panel colours in both themes.
- Research use only. De-identified, patient-derived data; no clinical claims. Repairs are proposals and the dashboard
  never modifies a release.
