"""Comparison runs: creation, background execution, persistence and dashboard summaries.

Each run lives in outputs/runs/<run_id>/:
    run.json               status, progress, validation result, summary (this record)
    findings.json          validated shared-format v0.2 document (only when valid)
    findings.invalid.json  kept when the validator rejects the engine's output
    engine_output.json     whatever the engine wrote itself
"""
from __future__ import annotations

import json
import threading
import traceback
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from backend import config
from backend.services import detector_adapter, inventory, report_export
from backend.services.releases import Release, get_release

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cct-run")
_lock = threading.RLock()
_runs: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_dir(run_id: str) -> Path:
    return config.RUNS_DIR / run_id


def _save(rec: dict) -> None:
    d = run_dir(rec["run_id"])
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "run.json.tmp"
    tmp.write_text(json.dumps(rec, indent=2, default=str))
    tmp.replace(d / "run.json")


def _update(run_id: str, **changes) -> dict:
    with _lock:
        rec = _runs[run_id]
        rec.update(changes)
        _save(rec)
        return dict(rec)


def _progress(run_id: str):
    def cb(msg: str) -> None:
        with _lock:
            rec = _runs.get(run_id)
            if rec is not None:
                rec["progress"] = (rec.get("progress") or []) + [f"{_now()} {msg}"]
                _save(rec)
    return cb


def load_existing() -> None:
    """Reload past runs at startup; runs interrupted by a restart become failed."""
    config.ensure_dirs()
    with _lock:
        for f in sorted(config.RUNS_DIR.glob("*/run.json")):
            try:
                rec = json.loads(f.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if rec.get("status") in ("pending", "running"):
                rec["status"] = "failed"
                rec["error"] = "The server stopped before this run finished. Start a new comparison."
                _save(rec)
            _runs[rec["run_id"]] = rec


def create_run(release_a: str, release_b: str, wait: bool = False) -> dict:
    rel_a, rel_b = get_release(release_a), get_release(release_b)  # ReleaseError -> 404/422
    _, info = detector_adapter.resolve()  # DetectorNotConfigured / DetectorError -> 503
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    rec = {"run_id": run_id, "status": "pending", "release_a": rel_a.name, "release_b": rel_b.name,
           "detector": info.to_dict(), "created_at": _now(), "started_at": None, "finished_at": None,
           "progress": [], "error": None, "validation": None, "findings_available": False,
           "verdict": None, "summary": None}
    with _lock:
        _runs[run_id] = rec
        _save(rec)
    fut = _executor.submit(_execute, run_id, rel_a, rel_b)
    if wait:
        fut.result()
    return get_run(run_id)


def _execute(run_id: str, rel_a: Release, rel_b: Release) -> None:
    _update(run_id, status="running", started_at=_now())
    progress = _progress(run_id)
    work = run_dir(run_id)
    try:
        progress(f"Calling detection engine with {rel_a.name} and {rel_b.name}")
        raw, info = detector_adapter.run(rel_a.path, rel_b.path, (rel_a.name, rel_b.name), work, progress)
        progress("Packaging findings.json (format v0.2)")
        doc, notes = report_export.build_document(raw, rel_a, rel_b, info.to_dict())
        progress("Validating with format/validate.py")
        target = work / "findings.json"
        errors = report_export.write_document(doc, target)
        summary = build_summary(doc, rel_a, rel_b, notes)
        if errors:
            target.replace(work / "findings.invalid.json")
            _update(run_id, status="failed", finished_at=_now(), detector=info.to_dict(), summary=summary,
                    validation={"valid": False, "errors": errors[:50], "validator": "format/validate.py"},
                    error=f"Engine output failed the official validator ({len(errors)} problem(s)); findings.json withheld.")
            return
        progress("Done: findings.json is valid")
        _update(run_id, status="completed", finished_at=_now(), detector=info.to_dict(),
                validation={"valid": True, "errors": [], "validator": "format/validate.py"},
                findings_available=True, verdict=doc.get("verdict"), summary=summary)
    except detector_adapter.DetectorError as e:
        _update(run_id, status="failed", finished_at=_now(), error=str(e))
    except Exception as e:  # unexpected: report honestly
        _update(run_id, status="failed", finished_at=_now(), error=f"{type(e).__name__}: {e}",
                traceback=traceback.format_exc(limit=4))


def get_run(run_id: str) -> dict:
    with _lock:
        rec = _runs.get(run_id)
        if rec is None:
            raise KeyError(run_id)
        return dict(rec)


def list_runs() -> list[dict]:
    with _lock:
        return sorted((dict(r) for r in _runs.values()), key=lambda r: r["created_at"], reverse=True)


def findings_path(run_id: str) -> Path | None:
    rec = get_run(run_id)
    p = run_dir(run_id) / "findings.json"
    if rec["status"] == "completed" and rec.get("findings_available") and p.is_file():
        return p
    return None


# ----------------------------------------------------------------------------- summary for the UI

def build_summary(doc: dict, rel_a: Release, rel_b: Release, notes: list[str]) -> dict:
    """Counts for the overview cards. Finding-based numbers are tallied from the ENGINE's findings
    (by `kind` and evidence pointers); file inventories come from the release files' id lists."""
    inv_a, inv_b = inventory.inventory(rel_a), inventory.inventory(rel_b)
    findings = doc.get("findings", [])
    kinds = Counter(f.get("kind", "other") for f in findings)
    sev = Counter(f.get("severity") for f in findings)

    def samples_in(kind: str) -> int:
        return len({e.get("id") for f in findings if f.get("kind") == kind
                    for e in f.get("evidence", []) if e.get("kind") == "sample"})

    review = [f["id"] for f in findings if f.get("needs_human_review")]
    # ids whose membership differs in at least one file present in both releases (the release-wide
    # added/removed counts miss a sample dropped from one file but still listed in another)
    per_file_changed: set[str] = set()
    for f in set(inv_a["per_file"]) & set(inv_b["per_file"]):
        a, b = inv_a["per_file"][f], inv_b["per_file"][f]
        if "error" not in a and "error" not in b:
            per_file_changed |= a["ids"] ^ b["ids"]
    return {
        "release_a": {"name": rel_a.name, "samples": len(inv_a["ids"]), "patients": inv_a["patients"],
                      "files_present": [f for f, v in rel_a.files.items() if v], "missing_required": rel_a.missing_required},
        "release_b": {"name": rel_b.name, "samples": len(inv_b["ids"]), "patients": inv_b["patients"],
                      "files_present": [f for f, v in rel_b.files.items() if v], "missing_required": rel_b.missing_required},
        "samples_added": len(inv_b["ids"] - inv_a["ids"]),
        "samples_removed": len(inv_a["ids"] - inv_b["ids"]),
        "samples_changed_in_any_file": len(per_file_changed),
        "files": inventory.membership_table(inv_a, inv_b),
        "metrics": {
            "total_findings": len(findings),
            "sample_swaps": kinds.get("sample_swap", 0), "samples_in_swaps": samples_in("sample_swap"),
            "duplicate_findings": kinds.get("duplicate", 0), "samples_in_duplicates": samples_in("duplicate"),
            "membership_changes": kinds.get("membership_change", 0),
            "missing_data_or_coverage": kinds.get("missing_data", 0),
            "label_conflicts": kinds.get("label_conflict", 0),
            "by_kind": dict(kinds), "by_severity": dict(sev),
        },
        "human_review_required": bool(review or doc.get("repairs")),
        "findings_needing_review": review,
        "verdict": doc.get("verdict"),
        "notes": notes,
    }
