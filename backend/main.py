"""Cohort Control Tower API (FastAPI).

Start:  uvicorn backend.main:app --port 8000      (from the repository root)
Docs:   http://127.0.0.1:8000/docs

Endpoints only move data between the dashboard, the release folders and the detection engine
(through services/detector_adapter.py). No detection or analysis logic lives here.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from backend import config
from backend.models import CompareRequest, HealthResponse, ReleaseInfo, RunList, RunRecord
from backend.services import comparison, detector_adapter, releases

VERSION = "0.4.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    comparison.load_existing()
    yield


app = FastAPI(title="Cohort Control Tower API", version=VERSION, lifespan=lifespan,
              description="Infrastructure API: discover TCGA-BRCA releases, run the team's detection engine, "
                          "serve validated findings.json (shared format v0.2).")


@app.exception_handler(releases.ReleaseError)
async def release_error_handler(request: Request, exc: releases.ReleaseError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(detector_adapter.DetectorError)
async def detector_error_handler(request: Request, exc: detector_adapter.DetectorError):
    return JSONResponse(status_code=503, content={"detail": f"Detection engine unavailable. {exc}"})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    msgs = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e.get("loc", []) if x != "body")
        msgs.append(f"{loc or 'request'}: {e.get('msg')}")
    return JSONResponse(status_code=422, content={"detail": "Invalid request. " + "; ".join(msgs)})


@app.get("/api/health", response_model=HealthResponse)
def health():
    """Readiness: baseline present, detector status (configured / auto / mock / not_configured / error), format files."""
    problems = []
    found = releases.discover()
    baseline = any(r.name == "baseline" for r in found)
    if not baseline:
        problems.append("Baseline release missing: run `python data/tcga-brca/fetch.py`.")
    det = detector_adapter.describe()
    if det.get("status") in ("not_configured", "error"):
        problems.append(det["error"])
    elif det.get("mock"):
        problems.append("Detector is the MOCK: results are placeholders, not findings.")
    schema_ok, validator_ok = config.SCHEMA_PATH.is_file(), config.VALIDATOR_PY.is_file()
    if not (schema_ok and validator_ok):
        problems.append("format/findings.schema.json or format/validate.py missing.")
    return {"status": "ok" if not problems else "degraded", "version": VERSION, "detector": det,
            "baseline_present": baseline, "releases_found": len(found), "schema_present": schema_ok,
            "validator_present": validator_ok, "problems": problems}


@app.get("/api/releases", response_model=list[ReleaseInfo])
def list_releases():
    """Releases discovered on disk (baseline, generated, opened envelopes, uploads) with file availability."""
    return [r.to_dict() for r in releases.discover()]


@app.get("/api/releases/{name}")
def release_detail(name: str):
    rel = releases.get_release(name)
    return {**rel.to_dict(), "provenance": releases.provenance(rel)}


@app.post("/api/releases/upload", response_model=ReleaseInfo, status_code=201)
def upload_release(name: str = Form(...), files: list[UploadFile] = File(...)):
    """Upload a release as the individual files or one .zip. Stored as `upload-<name>`."""
    rel = releases.save_upload(name, [(f.filename or "", f.file) for f in files])
    return rel.to_dict()


@app.post("/api/compare", response_model=RunRecord, status_code=202)
def compare(req: CompareRequest):
    """Start a comparison. 404 unknown release, 422 bad input, 503 engine not configured."""
    return comparison.create_run(req.release_a, req.release_b, wait=req.wait)


@app.get("/api/runs", response_model=RunList)
def runs():
    return {"runs": comparison.list_runs()}


@app.get("/api/runs/{run_id}", response_model=RunRecord)
def run_status(run_id: str):
    try:
        return comparison.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")


@app.get("/api/runs/{run_id}/findings")
def run_findings(run_id: str, download: bool = False):
    """The exact validated findings.json written for this run (byte-for-byte)."""
    try:
        rec = comparison.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    path = comparison.findings_path(run_id)
    if path is None:
        if rec["status"] in ("pending", "running"):
            raise HTTPException(status_code=409, detail=f"Run '{run_id}' is still {rec['status']}.")
        raise HTTPException(status_code=409, detail=f"Run '{run_id}' has no valid findings.json: {rec.get('error') or 'unknown error'}")
    headers = {"Content-Disposition": 'attachment; filename="findings.json"'} if download else None
    return FileResponse(path, media_type="application/json", headers=headers)

# --- Q&A over a finished run (logic lives in detection/qa.py; nothing here reads data) ---
from pydantic import BaseModel
 
 
class AskRequest(BaseModel):
    question: str = ""
    chip: str | None = None
 
 
@app.get("/api/qa/chips")
def qa_chips():
    from detection import qa
    return {"chips": [{"id": k, "label": v} for k, v in qa.CHIPS.items()], "free_text_available": qa.has_key()}
 
 
@app.post("/api/runs/{run_id}/ask")
def qa_ask(run_id: str, body: AskRequest):
    import json
    from detection import qa
    path = comparison.run_dir(run_id) / "findings.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No findings.json for this run (the run failed or does not exist).")
    return qa.ask(json.loads(path.read_text()), question=body.question, chip=body.chip)