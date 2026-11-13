# Cohort Control Tower — API, server and dashboard

Infrastructure for the Track 1 (Cohort Firewall) product: a FastAPI backend that discovers TCGA-BRCA
releases, calls the team's **detection engine** through one adapter, packages the engine's result as the
official `findings.json` (shared format v0.2), validates it with the organizers' validator, and a Streamlit
dashboard that shows the result and downloads the file.

**Scope.** This code moves data between the dashboard, the release folders and the detection engine. It
contains no detection, comparison, A1/A2 or repair logic; those come from the detection engine, which is a
separate component owned by other teammates.

Demo video: _link to be added before submission_.

```
Streamlit dashboard  --HTTP-->  FastAPI  --adapter-->  detection engine (teammates)  -->  findings.json
     frontend/app.py            backend/              backend/services/detector_adapter.py     outputs/runs/<id>/
```

| Part | Path |
|---|---|
| REST API + run storage | `backend/main.py`, `backend/services/{releases,comparison,report_export,inventory}.py` |
| Detector adapter (the integration point) | `backend/services/detector_adapter.py` |
| Labelled mock detector (testing only) | `backend/services/mock_detector.py` |
| Dashboard | `frontend/app.py` (+ `frontend/api_client.py`) |
| Infrastructure tests | `tests/test_api.py`, `tests/test_server.py` |
| Engine skeleton for teammates | `contrib/engine_template.py` |
| Opt-in reference detector (not used by default) | `contrib/baseline_detector/` |

---

## 1. Setup

```bash
git clone https://github.com/disleveK/oncosys-hackathon-challenge.git
cd oncosys-hackathon-challenge
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Python 3.11+ (tested on 3.13). Then the official data:

```bash
python data/tcga-brca/fetch.py                  # release A  -> data/tcga-brca/raw/
python data/tcga-brca/make_release.py           # practice B -> data/tcga-brca/releases/practice-B/
python data/tcga-brca/make_release.py --verify
```

Optional judging-day rehearsal (practice release without RNA, like the sealed envelopes):

```bash
python envelopes/unseal.py practice orange meadow pilot lantern   # -> envelopes/opened/practice/release/
```

## 2. Connect the detection engine

The API needs to know where the engine is. Three options:

| Option | What to do |
|---|---|
| Auto-discovery (zero config) | put the function in `detection/engine.py` as `analyze_releases(...)` |
| Environment variable | `CCT_DETECTOR="package.module:function"` or `CCT_DETECTOR="path/to/file.py:function"` |
| Isolated testing only | `CCT_DETECTOR=mock` (placeholder output, labelled MOCK everywhere) |

Without one of these, `/api/health` reports `detector.status = "not_configured"`, the dashboard disables
**Compare**, and `POST /api/compare` answers `503`. Nothing is substituted.

```bash
# macOS / Linux
export CCT_DETECTOR="detection.engine:analyze_releases"
# Windows PowerShell
$env:CCT_DETECTOR = "detection.engine:analyze_releases"
```

## 3. Start the backend

```bash
uvicorn backend.main:app --port 8000        # from the repository root
```

API docs: http://127.0.0.1:8000/docs · health: http://127.0.0.1:8000/api/health

## 4. Start the dashboard (second terminal)

```bash
streamlit run frontend/app.py
```

Open http://localhost:8501. The sidebar shows API status and which detector is connected (or MOCK / not
configured). `CCT_API_URL` changes the API address.

## 5. Use it

1. Select Release A (`baseline`) and Release B (`practice-B`, `envelope-practice`, an opened envelope, or an upload).
   The table shows which of the five required files and the optional RNA file each release has.
2. **Compare releases**. Progress lines from the engine appear live.
3. Result page: verdict, human-review banner, metric cards, per-file sample-id table, then tabs
   **Findings** (filter, search, open one finding with its evidence pointers), **Analysis impact** (A1/A2 status
   and before/after exactly as the engine reported them), **Repairs & review**, **Provenance** (SHA-256 per file
   per release), raw JSON.
4. **Download findings.json**: the exact bytes the backend validated.

Validate the download yourself:

```bash
python format/validate.py findings-<run_id>.json
```

## 6. Judging day

```bash
python envelopes/unseal.py 07 word1 word2 word3 word4     # number and words come from the judge
```

The opened release appears as `envelope-E07` in the dashboard (folders are rescanned on every request).
Select `baseline` → `envelope-E07`, Compare, Download. No code changes between runs.

Other releases can be added from the dashboard ("Add a release": the five files or one .zip) or with
`POST /api/releases/upload`; they are stored as `upload-<name>` under `outputs/uploads/`.

## 7. Smoke test without the UI

```bash
uvicorn backend.main:app --port 8000 &
curl -s localhost:8000/api/health
curl -s -X POST localhost:8000/api/compare -H "content-type: application/json" \
     -d '{"release_a":"baseline","release_b":"practice-B","wait":true}' > run.json
python -c "import json;r=json.load(open('run.json'));print(r['status'],r['verdict'],r['validation'],r['error'])"
RUN=$(python -c "import json;print(json.load(open('run.json'))['run_id'])")
curl -s localhost:8000/api/runs/$RUN/findings -o findings.json
python format/validate.py findings.json
```

## 8. Tests

```bash
pytest -q        # 35 infrastructure tests, ~7 s, no data download needed
```

They use small synthetic release folders, the labelled mock and fake engines (`tests/fake_engines.py`).
Covered: server startup (TestClient lifespan and a real `uvicorn` process), config paths, health states,
release discovery (baseline / generated / envelope / upload, missing files, no RNA), request validation (422),
unknown release (404), engine not configured (503), adapter resolution order (env → auto → mock),
positional and keyword engine signatures, engine returning `None` + file, numpy values, pass-through of
findings/analyses/repairs/verdict, official validator on the exported file, engine crash / invalid output /
non-dict result / bad import all reported as failed with the reason, run persistence across restart,
unknown run (404), byte-exact download, frontend client against the API, upload safety.

They do not test whether any detector is scientifically right; that belongs with the engine.

---

## API reference

| Method & path | Purpose | Errors |
|---|---|---|
| `GET /api/health` | `status`, `version`, `detector{status: configured|auto|mock|not_configured|error, name, error}`, `baseline_present`, `problems[]` | |
| `GET /api/releases` | discovered releases: `name`, `origin`, `location`, `files{name: bool}`, `missing_required[]`, `has_rna`, `comparable` | |
| `GET /api/releases/{name}` | one release + `provenance.files[]` (sha256, bytes, matches official baseline) | 404 |
| `POST /api/releases/upload` | multipart `name` + `files` (five files or one .zip) → `201` release | 400 unsafe path, 409 exists, 413 too big, 422 unknown file |
| `POST /api/compare` | body `{"release_a","release_b","wait":false}` → `202` run record | 404 unknown release, 422 bad body, 503 engine unavailable |
| `GET /api/runs` | all runs, newest first | |
| `GET /api/runs/{run_id}` | `status` (`pending`/`running`/`completed`/`failed`), `progress[]`, `detector`, `validation`, `summary`, `error` | 404 |
| `GET /api/runs/{run_id}/findings` | the validated `findings.json`; `?download=true` adds attachment headers | 404 unknown, 409 not available (running or failed) |

Release names are discovered from folders; clients never pass filesystem paths. Error bodies are
`{"detail": "..."}`.

Run folder: `outputs/runs/<run_id>/` → `run.json` (record), `findings.json` (only when valid),
`findings.invalid.json` (when the validator rejected the engine's output), `engine_output.json` (whatever the
engine wrote).

`summary` (for the dashboard cards) is bookkeeping only: sample-id counts read from each file's header /
first column, and tallies of the engine's findings by `kind` and evidence pointers.

### Environment variables

| Variable | Meaning | Default |
|---|---|---|
| `CCT_DETECTOR` | engine location: `module:function`, `file.py:function`, or `mock` | unset → auto-discover `detection/engine.py` |
| `CCT_TEAM` | `producer.team` in findings.json | `Cohort Control Tower team` |
| `CCT_OUTPUT_DIR` | runs and uploads | `outputs/` |
| `CCT_MAX_UPLOAD_MB` | per-file upload limit | 200 |
| `CCT_API_URL` | API base for the dashboard | `http://127.0.0.1:8000` |

---

## Detection engine contract (for the detection teammates)

One Python function. Skeleton to copy: `contrib/engine_template.py`.

```python
def analyze_releases(release_a: str, release_b: str, output_path: str) -> dict:
    """
    release_a, release_b : folder paths. Each holds clinical.tsv, survival.tsv, mutation_gene_level.tsv.gz,
                           protein_rppa.tsv.gz, copy_number_gistic.tsv.gz and maybe rna_hiseq.tsv.gz.
                           Do not assume the same sample ids in both, or that RNA exists.
    output_path          : a path inside the run folder; write your own JSON there if useful.
                           If you return None the adapter reads this file instead.
    returns              : dict in shared-format v0.2 shape:
                             {"findings": [...],                       # required
                              "analyses": [...], "repairs": [...],      # optional, shown in the dashboard
                              "verdict": "Blocked", "question": "..."}  # optional
                           A complete v0.2 document is also accepted.
    on failure           : raise. The run is marked failed with your message; nothing is substituted.
    """
```

Optional keyword arguments, passed only when the signature declares them (or `**kwargs`):
`release_names=(name_a, name_b)` (display names for evidence pointers) and `progress=callable(str)`
(live progress lines in the dashboard).

What the backend does with the result:

1. Adds the envelope: `format_version: "0.2"`, `producer` (team, product, track `cohort-firewall`, `engine`),
   `data` (both releases with SHA-256 per file: file hash for the baseline, decompressed-content hash for `.gz`
   files of other releases, the `make_release.py` convention), and `question` if you did not supply one.
2. Passes `findings`, `analyses`, `repairs`, `decisions`, `verdict` (if an allowed value) through **unchanged**.
   It never adds, removes or rewrites findings, analyses or repairs.
3. Runs `format/validate.py`. If it fails, the run is `failed`, the messages are in `run.json → validation.errors`
   and the document is kept as `findings.invalid.json` for debugging.

Field values the schema accepts (see `format/findings.schema.json`): finding `kind` ∈ sample_swap, duplicate,
missing_data, membership_change, label_conflict, join_inflation, unlinked_record, claim_check, other;
`severity` ∈ high, medium, low, none; `confidence` ∈ high, medium, low; evidence `kind` ∈ sample, patient, gene,
protein, slide, file, release, analysis, claim, row; analysis `status` ∈ unchanged, changed, not_rerun; repair
`action` ∈ exclude, relabel, restore_from_previous_release, flag_for_review, other; every `repairs[].addresses`
id must be a finding id; `verdict` ∈ Ready, Conditional, Blocked, Insufficient Evidence (or Proceed, Fix a
problem, Narrow the question, Stop).

Dashboard conventions (all optional, nothing breaks without them): a finding's `file`, `details` (any dict,
shown under "Engine details") and `impact_reasons` (`{"A1": "why", "A2": "why"}`); an analysis's `title`,
`inputs`, `triggered_by`, `reason`, `comparison`, `after_excluding_flagged`.

Quick check of an engine without the UI:

```bash
CCT_DETECTOR="detection.engine:analyze_releases" pytest -q tests/test_api.py -k "engine_results_pass_through"   # contract shape
CCT_DETECTOR="detection.engine:analyze_releases" uvicorn backend.main:app --port 8000                          # then section 7
```

### `contrib/baseline_detector/` (opt-in reference, not the team engine)

A self-contained example that satisfies the contract on the real files (fingerprints, membership, swaps,
duplicates, missing values, A1/A2 reruns via the organizers' `reference_analyses.py`). It is **never** used unless
explicitly selected with `CCT_DETECTOR="contrib.baseline_detector.engine:analyze_releases"`, and it labels itself
`contrib-baseline-reference` in `producer.engine`. Teammates may borrow from it or ignore it.

---

## Safety

De-identified, patient-derived research data: no re-identification, no clinical claims, no automatic repairs
(the dashboard shows repairs as proposals requiring human review). Raw TCGA files, generated releases, opened
envelopes, run outputs and uploads are git-ignored. No credentials. The application never opens `CHANGES.json`.
