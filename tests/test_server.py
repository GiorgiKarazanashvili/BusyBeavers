"""Server-level tests: startup, configuration, adapter resolution, run persistence, export packaging."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from tests.conftest import REPO


def test_app_starts_with_lifespan(client):
    """TestClient context runs the lifespan (dirs created, past runs loaded)."""
    from backend import config
    assert config.RUNS_DIR.is_dir() and config.UPLOADS_DIR.is_dir()
    assert client.get("/docs").status_code == 200


def test_real_uvicorn_process_boots(tmp_path):
    """Start the actual server command from the README and hit /api/health."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {"PATH": "/usr/bin:/bin", "CCT_OUTPUT_DIR": str(tmp_path), "CCT_DETECTOR": "mock",
           "PYTHONPATH": str(REPO), "SYSTEMROOT": "", "HOME": str(tmp_path)}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(port)],
                            cwd=REPO, env={k: v for k, v in env.items() if v}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        body = None
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as r:
                    body = json.loads(r.read())
                    break
            except Exception:
                time.sleep(0.5)
        assert body is not None, proc.stdout.read().decode(errors="replace")[-2000:]
        assert body["detector"]["status"] == "mock" and body["version"]
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_config_paths_are_repo_relative():
    from backend import config
    assert config.REPO_ROOT == REPO
    assert config.SCHEMA_PATH == REPO / "format" / "findings.schema.json"
    assert config.VALIDATOR_PY.is_file() and config.SCHEMA_PATH.is_file()
    assert set(config.REQUIRED_FILES) == {"clinical.tsv", "survival.tsv", "mutation_gene_level.tsv.gz",
                                          "protein_rppa.tsv.gz", "copy_number_gistic.tsv.gz"}
    assert "rna_hiseq.tsv.gz" in config.OPTIONAL_FILES


def test_adapter_resolution_order(env, set_detector, monkeypatch):
    from backend.services import detector_adapter as da
    set_detector("mock")
    fn, info = da.resolve()
    assert info.mock and info.source == "mock"
    set_detector("tests.fake_engines:full_engine")
    fn, info = da.resolve()
    assert info.source == "env" and fn.__name__ == "full_engine"
    set_detector("")
    with pytest.raises(da.DetectorNotConfigured):
        da.resolve()
    # auto-discovery: a detection/engine.py in a temp package on sys.path
    pkg = env / "detection"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "engine.py").write_text("def analyze_releases(a, b, out):\n    return {'findings': []}\n")
    monkeypatch.syspath_prepend(str(env))
    fn, info = da.resolve()
    assert info.source == "auto" and info.spec == "detection.engine:analyze_releases"
    assert da.describe()["status"] == "auto"


def test_runs_persist_across_restart(env, set_detector):
    from backend.services import comparison
    set_detector("mock")
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as c:
        rid = c.post("/api/compare", json={"release_a": "baseline", "release_b": "other", "wait": True}).json()["run_id"]
    # simulate a crash mid-run on disk
    stuck = json.loads((env / "outputs" / "runs" / rid / "run.json").read_text())
    stuck["run_id"] = rid + "-stuck"
    stuck["status"] = "running"
    (env / "outputs" / "runs" / stuck["run_id"]).mkdir()
    (env / "outputs" / "runs" / stuck["run_id"] / "run.json").write_text(json.dumps(stuck))
    comparison._runs.clear()
    with TestClient(app) as c:
        runs = {r["run_id"]: r for r in c.get("/api/runs").json()["runs"]}
        assert runs[rid]["status"] == "completed"
        assert c.get(f"/api/runs/{rid}/findings").status_code == 200
        assert runs[rid + "-stuck"]["status"] == "failed" and "server stopped" in runs[rid + "-stuck"]["error"]


def test_build_document_envelope_only(env):
    """report_export adds the envelope and passes the engine's science through unchanged."""
    from backend.services import report_export
    from backend.services.releases import get_release
    a, b = get_release("baseline"), get_release("norna")
    raw = {"findings": [{"id": "F", "summary": "s", "severity": "low", "confidence": "low",
                         "evidence": [{"kind": "file", "id": "clinical.tsv"}]}],
           "analyses": [{"id": "A2", "status": "unchanged", "before": {"x": 1}, "after": {"x": 1}}],
           "repairs": [], "verdict": "Conditional", "question": "engine question", "producer": {"team": "detectors"}}
    doc, notes = report_export.build_document(raw, a, b, {"name": "x:y", "mock": False})
    assert doc["format_version"] == "0.2" and doc["question"] == "engine question"
    assert doc["findings"] == raw["findings"] and doc["analyses"] == raw["analyses"] and doc["verdict"] == "Conditional"
    assert doc["producer"]["engine"] == "x:y" and doc["producer"]["engine_producer"] == {"team": "detectors"}
    names = {r["name"]: r for r in doc["data"]["releases"]}
    assert "rna_hiseq.tsv.gz" in {f["file"] for f in names["baseline"]["files"]}
    assert "rna_hiseq.tsv.gz" not in {f["file"] for f in names["norna"]["files"]}
    assert all(f["hash_of"] == "file" for f in names["baseline"]["files"])
    assert any(f["hash_of"] == "content" for f in names["norna"]["files"] if f["file"].endswith(".gz"))
    assert notes == []
    out = env / "doc.json"
    assert report_export.write_document(doc, out) == []


def test_validator_rejects_bad_document(env):
    from backend.services import report_export
    out = env / "bad.json"
    out.write_text(json.dumps({"format_version": "0.1", "producer": {}, "data": {}, "question": "q",
                               "findings": [{"id": "F", "summary": "s", "severity": "catastrophic", "confidence": "high",
                                             "evidence": []}]}))
    errors = report_export.validate_file(out)
    assert len(errors) >= 3 and any("format_version" in e for e in errors) and any("severity" in e for e in errors)


def test_release_without_rna_and_partial_release(client):
    rels = {r["name"]: r for r in client.get("/api/releases").json()}
    assert rels["norna"]["files"]["rna_hiseq.tsv.gz"] is False
    rec = client.post("/api/compare", json={"release_a": "baseline", "release_b": "norna", "wait": True}).json()
    assert rec["status"] == "completed"
    rec = client.post("/api/compare", json={"release_a": "baseline", "release_b": "partial", "wait": True}).json()
    assert rec["status"] == "completed" and rec["summary"]["release_b"]["missing_required"] == ["survival.tsv"]


def test_summary_inventory_flags_equal_count_different_members(client):
    rec = client.post("/api/compare", json={"release_a": "baseline", "release_b": "other", "wait": True}).json()
    f = rec["summary"]["files"]["clinical.tsv"]
    assert f["samples_a"] == f["samples_b"] and f["count_equal_membership_differs"] is True
    assert rec["summary"]["samples_added"] == 1 and rec["summary"]["samples_removed"] == 1
