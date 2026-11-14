# Deploy the Cohort Control Tower as a website (Streamlit Community Cloud)

Goal: the `BusyBeavers` repository opens as a public website that runs **its own backend and frontend**:
the FastAPI server in `backend/` (with `detection/engine.py` auto-discovered) and the Streamlit dashboard in
`frontend/`. Hosting is free, the repository can stay private, and deploys follow every push to `main`.

**Why this host.** Streamlit Community Cloud is the only free host that deploys a *private* GitHub repository with
nothing more than a click, and it runs one container per app. It starts one command (`streamlit run frontend/app.py`),
so the dashboard now starts the repository's API itself: on load it checks `http://127.0.0.1:8000`, and when nothing
answers it launches `python -m uvicorn backend.main:app --port 8000` as a child process in the same container, waits
for `/api/health`, and then talks to it over HTTP exactly as it does on a laptop with two terminals. Nothing in
`backend/` or `detection/` changes and no request bypasses the API. (A Dockerfile on Render or Hugging Face would do
the same with two processes, but needs a card on file or a separate git remote; not worth it for a demo.)

On the very first start the app also downloads the official baseline (5 files, ~6 MB, checksum-verified by the
organizers' `data/tcga-brca/fetch.py --no-rna`) and builds `practice-B` with `data/tcga-brca/make_release.py`,
because raw data is git-ignored. This takes a few seconds and is shown on the page.

## 1. What changes in the repository

The zip `busybeavers-frontend-cloud.zip` contains only these files:

| File | Change |
|---|---|
| `frontend/app.py` | `resolve_backend()` starts the sidecar when no API answers; status shows `API (sidecar)`; Engine page shows the backend process |
| `frontend/local_backend.py` | **new**: data bootstrap + uvicorn sidecar launcher (`CCT_MODE` auto / http / sidecar) |
| `frontend/requirements.txt` | **new**: what Community Cloud installs (streamlit, fastapi, uvicorn, pydantic, python-multipart, pandas, numpy, jsonschema, requests) |
| `frontend/README.md` | new section "Deploy as a website" |
| `.streamlit/config.toml` | the dashboard theme (dark brown base); your clone did not have it |

`backend/`, `detection/`, `tests/` and the root `requirements.txt` are untouched. The two-terminal workflow
(`uvicorn …` + `streamlit run …`) keeps working unchanged: when the API already answers, nothing is started.

Checked here: headless run against your repository copy with no API running → the dashboard started uvicorn,
`baseline` vs `practice-B` completed with your engine (verdict Conditional, findings and repairs rendered), the
sidecar survived page reruns as a single process, and the first-start bootstrap fetched the five files and built
`practice-B` in a copy without data. The 40 tests of the infrastructure suite pass.

## 2. Push the files (Windows PowerShell)

Download `busybeavers-frontend-cloud.zip` to your Downloads folder, then:

```powershell
cd "C:\Users\Khoi Le\BusyBeavers"
git pull
Expand-Archive -Path "$env:USERPROFILE\Downloads\busybeavers-frontend-cloud.zip" -DestinationPath . -Force
git status                       # expect: frontend/app.py, frontend/local_backend.py, frontend/requirements.txt, frontend/README.md, .streamlit/config.toml
git add frontend .streamlit
git commit -m "Run the dashboard with its backend as a sidecar on Streamlit Community Cloud"
git push
```

Optional local check before pushing (one terminal, no uvicorn):

```powershell
.\.venv\Scripts\Activate.ps1
pip install uvicorn
python -m streamlit run frontend\app.py
```

The top bar should read `API (sidecar) v0.2.0 · engine: auto-discovered`.

## 3. Deploy on share.streamlit.io (click by click)

1. Open **https://share.streamlit.io** and click **Continue with GitHub**. Sign in with the GitHub account that has
   access to `GiorgiKarazanashvili/BusyBeavers` (yours, as a collaborator, is enough).
2. GitHub asks to **Authorize Streamlit**. Because the repository is private, Streamlit must be allowed to read it:
   on the authorization page, under *Organization access* / *Repository access*, grant access to the owner of
   the repository. If the owner is Giorgi's personal account and you are only a collaborator, Giorgi has to do this
   step once (or install the Streamlit app for the repository): **Settings → Applications → Streamlit → Repository
   access → Only select repositories → BusyBeavers**. Without it, Community Cloud lists the repository as not found.
3. Back on share.streamlit.io, click **Create app** (top right) → **Deploy a public app from GitHub**.
4. Fill in the form:
   - **Repository**: `GiorgiKarazanashvili/BusyBeavers`
   - **Branch**: `main`
   - **Main file path**: `frontend/app.py`
   - **App URL**: pick a name, for example `busybeavers-cohort-control-tower` → `https://busybeavers-cohort-control-tower.streamlit.app`
5. Click **Advanced settings**:
   - **Python version**: `3.12`
   - **Secrets**: leave empty. (Only if you ever want to force the mode, add `CCT_MODE = "sidecar"`.)
   - Click **Save**.
6. Click **Deploy**. The first build installs `frontend/requirements.txt` (2–4 minutes). Then the page shows
   "First start: preparing the official data" for a few seconds, then the dashboard with
   `API (sidecar) · engine: auto-discovered` in the top bar.
7. Test it: Select release → `baseline` vs `practice-B` → **Compare releases**. Results, Next steps and
   **Download findings.json** work exactly as locally.
8. Share the `.streamlit.app` URL (and put it in `CONTROL_TOWER_README.md`). Every push to `main` redeploys
   automatically. "Manage app" (bottom right of the live page) shows the logs if anything goes wrong.

## 4. Things to know

- **Sleep**: a free app sleeps after a few days without visitors and wakes on the first visit (about a minute,
  re-downloading the data). Open it once before the demo.
- **Runs are not persistent**: `outputs/` lives in the container. A reboot or a new commit clears past runs and
  uploads. Start a fresh comparison for the demo; it takes seconds.
- **Resources**: Community Cloud gives about 2.7 GB RAM. The official data without RNA is small, so the engine
  comfortably fits. Uploaded releases are limited by the backend's `CCT_MAX_UPLOAD_MB` (default 200).
- **Dependencies**: if the build log says a package is missing, add it to `frontend/requirements.txt` and push.
  If Community Cloud picks the root `requirements.txt` instead (it prefers the one next to the main file), remove
  the heavy notebook-only lines (`idc-index`, `jupyter`) from the root file or keep the two in sync.
- **Nothing is public that was not already**: the app shows only what the API returns; `data/tcga-brca/raw` is
  downloaded from UCSC Xena at start and is never committed.
