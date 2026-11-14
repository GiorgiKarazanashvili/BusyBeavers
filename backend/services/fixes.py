"""Easy fixes: person-started, undoable edits to a run's release B.

The dashboard's one-click "Remove" (exclude a record) and typed "Apply" (relabel a field) land here.
Nothing is changed in place:

  * every fix is appended to outputs/runs/<run_id>/fixes.json (an audit log; undo marks an entry
    "undone", it never deletes it);
  * the run's validated findings.json is never rewritten (it stays byte-for-byte what the validator saw);
  * release B's folder is never touched. `build_dataset()` returns a zip of release B with the fixes
    applied: mode "easy" = one-click removals only, mode "user" = removals + labels typed by a person.

Fix request body (what frontend/app.py posts):
    {"finding_id": "F03", "repair_id": "R03" | null, "action": "exclude" | "relabel",
     "record_id": "TCGA-..", "file": "clinical.tsv", "field": "<column>" (relabel), "new_value": "..." (relabel),
     "actor": "optional free text"}
"""
from __future__ import annotations

import gzip
import io
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backend import config
from backend.services import comparison
from backend.services.releases import Release, get_release

ACTIONS = ("exclude", "relabel")
RECORD_KINDS = ("sample", "patient", "row")
ROW_TABLES = {"clinical.tsv": "sampleID", "survival.tsv": "sample"}  # id column of each row table
MAX_VALUE_LEN = 200

_lock = threading.RLock()


class FixError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.message, self.status_code = message, status_code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ----------------------------------------------------------------------------- storage

def _log_path(run_id: str) -> Path:
    return comparison.run_dir(run_id) / "fixes.json"


def _read_log(run_id: str) -> dict:
    p = _log_path(run_id)
    if not p.is_file():
        return {"run_id": run_id, "fixes": []}
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise FixError(f"fixes.json for run '{run_id}' is unreadable: {e}", 500) from e


def _write_log(run_id: str, log: dict) -> None:
    p = _log_path(run_id)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    tmp.replace(p)


def _completed_run(run_id: str) -> tuple[dict, dict]:
    """(run record, findings document) or FixError 404/409."""
    try:
        rec = comparison.get_run(run_id)
    except KeyError:
        raise FixError(f"Run '{run_id}' not found.", 404)
    path = comparison.findings_path(run_id)
    if path is None:
        raise FixError(f"Run '{run_id}' has no valid findings.json (status: {rec['status']}); nothing to fix.", 409)
    return rec, json.loads(path.read_text())


# ----------------------------------------------------------------------------- queries

def list_fixes(run_id: str, include_undone: bool = False) -> list[dict]:
    _completed_run(run_id)
    with _lock:
        fixes = _read_log(run_id)["fixes"]
    return fixes if include_undone else [f for f in fixes if f.get("status") == "applied"]


def _active(run_id: str) -> list[dict]:
    return [f for f in _read_log(run_id)["fixes"] if f.get("status") == "applied"]


# ----------------------------------------------------------------------------- validation helpers

def _finding_records(finding: dict) -> dict[str, dict]:
    """record id -> pointer, from the finding's evidence and from an explicit finding['fix'] block."""
    out: dict[str, dict] = {}
    for e in finding.get("evidence", []):
        if e.get("kind") in RECORD_KINDS and e.get("id"):
            out.setdefault(e["id"], e)
    given = finding.get("fix")
    if isinstance(given, dict):
        for t in given.get("targets", []):
            if t.get("id"):
                out.setdefault(t["id"], t)
    return out


def _resolve_files(requested: str | None, pointer: dict, finding: dict, rel_b: Release) -> list[str]:
    """The release-B file(s) a fix applies to. The dashboard may send 'a.tsv, b.tsv' (a finding over files)."""
    names = [x.strip() for x in (requested or "").split(",") if x.strip()]
    if not names and pointer.get("file"):
        names = [pointer["file"]]
    if not names and finding.get("file"):
        names = [finding["file"]]
    bad = [n for n in names if n not in config.KNOWN_FILES]
    if bad:
        raise FixError(f"Unknown file(s) {bad}. Known files: {', '.join(config.KNOWN_FILES)}.")
    present = [n for n in names if rel_b.files.get(n)]
    if not present:
        raise FixError(f"None of {names or ['(no file given)']} exists in release '{rel_b.name}'.")
    return present


def _read_table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, low_memory=False)


def _current_value(rel_b: Release, file: str, record_id: str, field: str) -> str:
    if file not in ROW_TABLES:
        raise FixError(f"Relabel works on row tables ({', '.join(ROW_TABLES)}); '{file}' is a measurement matrix. "
                       "Use exclude, or leave it for a researcher.")
    df = _read_table(rel_b.file_path(file))
    id_col = df.columns[0]
    if field == id_col or field == ROW_TABLES[file]:
        raise FixError(f"'{field}' is the id column of {file}; ids cannot be relabelled here.")
    if field not in df.columns:
        raise FixError(f"Column '{field}' is not in {file} of release '{rel_b.name}'.")
    rows = df.index[df[id_col] == record_id]
    if len(rows) == 0:
        raise FixError(f"Record '{record_id}' is not in {file} of release '{rel_b.name}'.")
    vals = sorted(set(df.loc[rows, field]))
    return vals[0] if len(vals) == 1 else " | ".join(vals)


# ----------------------------------------------------------------------------- apply / undo

def apply_fix(run_id: str, body: dict) -> dict:
    rec, doc = _completed_run(run_id)
    action = body.get("action")
    if action not in ACTIONS:
        raise FixError(f"action must be one of {ACTIONS}, got {action!r}.")
    fid, record_id = body.get("finding_id"), (body.get("record_id") or "").strip()
    finding = next((f for f in doc.get("findings", []) if f.get("id") == fid), None)
    if finding is None:
        raise FixError(f"Finding '{fid}' is not in this run's findings.json.", 404)
    records = _finding_records(finding)
    if record_id not in records:
        raise FixError(f"Record '{record_id}' is not part of the evidence of {fid}; fixes only touch flagged records.")
    repair_id = body.get("repair_id")
    if repair_id is not None:
        repair = next((r for r in doc.get("repairs", []) if r.get("id") == repair_id), None)
        if repair is None:
            raise FixError(f"Repair '{repair_id}' is not in this run's findings.json.", 404)
        if fid not in repair.get("addresses", []):
            raise FixError(f"Repair '{repair_id}' does not address finding {fid}.")

    rel_b = get_release(rec["release_b"])
    files = _resolve_files(body.get("file"), records[record_id], finding, rel_b)
    entry = {"finding_id": fid, "repair_id": repair_id, "action": action, "record_id": record_id,
             "file": ", ".join(files), "files": files}
    if action == "relabel":
        field, new_value = (body.get("field") or "").strip(), str(body.get("new_value") or "").strip()
        if not field or not new_value:
            raise FixError("relabel needs a 'field' and a non-empty 'new_value'.")
        if len(new_value) > MAX_VALUE_LEN or any(c in new_value for c in "\t\r\n"):
            raise FixError(f"new_value must be one line, no tabs, at most {MAX_VALUE_LEN} characters.")
        if len(files) != 1:
            raise FixError("relabel applies to exactly one file.")
        old = _current_value(rel_b, files[0], record_id, field)
        if old == new_value:
            raise FixError(f"{record_id} already has {field} = '{new_value}' in release B.")
        entry.update(field=field, old_value=old, new_value=new_value)

    with _lock:
        log = _read_log(run_id)
        for x in log["fixes"]:
            if x.get("status") != "applied":
                continue
            if x["finding_id"] == fid and x["record_id"] == record_id:
                raise FixError(f"{record_id} already has an active fix for {fid} ({x['fix_id']}); undo it first.", 409)
            if (action == "relabel" and x["action"] == "relabel" and x["record_id"] == record_id
                    and x.get("field") == entry["field"] and x.get("files") == files):
                raise FixError(f"{record_id}.{entry['field']} is already relabelled by {x['fix_id']}; undo it first.", 409)
            if x["action"] == "exclude" and x["record_id"] == record_id and set(x.get("files", [])) & set(files):
                raise FixError(f"{record_id} is already excluded from {x['file']} by {x['fix_id']}.", 409)
        n = len(log["fixes"]) + 1
        entry = {"fix_id": f"X{n:03d}", "status": "applied", "applied_at": _now(),
                 "actor": str(body.get("actor") or "dashboard user")[:80], **entry}
        log["fixes"].append(entry)
        _write_log(run_id, log)
    return entry


def undo_fix(run_id: str, fix_id: str) -> dict:
    _completed_run(run_id)
    with _lock:
        log = _read_log(run_id)
        x = next((f for f in log["fixes"] if f.get("fix_id") == fix_id), None)
        if x is None:
            raise FixError(f"Fix '{fix_id}' not found for run '{run_id}'.", 404)
        if x.get("status") != "applied":
            raise FixError(f"Fix '{fix_id}' is already {x.get('status')}.", 409)
        x.update(status="undone", undone_at=_now())
        _write_log(run_id, log)
        return x


# ----------------------------------------------------------------------------- fixed dataset download

MODES = ("easy", "user")  # easy: every rule-based removal the engine proposed; user: the person's removals + typed labels


def _suggested_removals(doc: dict, rel_b: Release) -> list[dict]:
    """The engine's own `exclude` repairs from findings.json, as fix-like entries. No person involved."""
    out, seen = [], set()
    for r in doc.get("repairs", []):
        if r.get("action") != "exclude":
            continue
        for t in r.get("targets", []):
            file = t.get("file")
            if t.get("kind") not in RECORD_KINDS or not t.get("id") or file not in config.KNOWN_FILES or not rel_b.files.get(file):
                continue
            if (t["id"], file) in seen:
                continue
            seen.add((t["id"], file))
            out.append({"repair_id": r.get("id"), "finding_id": ",".join(r.get("addresses", [])), "action": "exclude",
                        "record_id": t["id"], "file": file, "files": [file], "source": "engine suggestion"})
    return out


def _write_tsv(df: pd.DataFrame, path: Path, index: bool) -> None:
    text = df.to_csv(sep="\t", index=index, lineterminator="\n")
    if path.name.endswith(".gz"):
        with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as gz:
            gz.write(text.encode("utf-8"))
    else:
        path.write_text(text, encoding="utf-8")


def _patch_file(src: Path, dst: Path, file: str, excludes: set[str], relabels: list[dict]) -> dict:
    if file in ROW_TABLES:
        df = _read_table(src)
        id_col = df.columns[0]
        before = len(df)
        for r in relabels:
            df.loc[df[id_col] == r["record_id"], r["field"]] = r["new_value"]
        df = df[~df[id_col].isin(excludes)]
        _write_tsv(df, dst, index=False)
        return {"rows_removed": before - len(df), "cells_relabelled": len(relabels)}
    df = pd.read_csv(src, sep="\t", dtype=str, keep_default_na=False, index_col=0, low_memory=False)
    drop = [c for c in df.columns if c in excludes]
    _write_tsv(df.drop(columns=drop), dst, index=True)
    return {"columns_removed": len(drop)}


def build_dataset(run_id: str, mode: str) -> tuple[bytes, str]:
    """Zip of release B with the run's applied fixes. Release B itself is never modified.

    mode "easy": every `exclude` repair the engine proposed (rule-based, no clicks needed);
    mode "user": the removals and typed labels a person applied in the dashboard.
    Returns (zip bytes, file name)."""
    if mode not in MODES:
        raise FixError(f"mode must be one of {sorted(MODES)}, got {mode!r}.")
    rec, doc = _completed_run(run_id)
    rel_b = get_release(rec["release_b"])
    if mode == "easy":
        active = _suggested_removals(doc, rel_b)
        if not active:
            raise FixError("The engine proposed no removals for this run; the dataset would equal "
                           f"release {rel_b.name}.", 409)
    else:
        with _lock:
            active = _active(run_id)
        if not active:
            raise FixError(f"No applied fixes for this run yet; the dataset would equal release {rel_b.name}.", 409)

    import tempfile
    import zipfile
    folder = f"{rel_b.name}-{mode}-fixed"
    changes: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for file, present in rel_b.files.items():
                if not present:
                    continue
                excl = {x["record_id"] for x in active if x["action"] == "exclude" and file in x["files"]}
                rel = [x for x in active if x["action"] == "relabel" and file in x["files"]]
                if excl or rel:
                    changes[file] = _patch_file(rel_b.file_path(file), tmp / file, file, excl, rel)
                    z.write(tmp / file, f"{folder}/{file}")
                else:  # untouched files go in byte-identical to release B
                    z.write(rel_b.file_path(file), f"{folder}/{file}")
            manifest = {"built_at": _now(), "run_id": run_id, "mode": mode, "release_a": rec["release_a"],
                        "source_release": rel_b.name, "files_changed": changes, "fixes": active,
                        "note": f"Copy of {rel_b.name} with the fixes below; the original release was not modified."}
            z.writestr(f"{folder}/FIXES_APPLIED.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    return buf.getvalue(), f"{folder}.zip"
