"""API contract tests (run from the repository root: pytest -q).

The detector is the labelled MOCK unless a test configures a fake engine. No scientific
correctness is asserted anywhere: these tests check that requests, runs, files and errors flow
through the infrastructure correctly.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import zipfile

import pytest

from tests.conftest import REPO


def _run(client, a="baseline", b="other"):
    r = client.post("/api/compare", json={"release_a": a, "release_b": b, "wait": True})
    assert r.status_code == 202, r.text
    return r.json()


# --- health -------------------------------------------------------------------------------

def test_health_reports_mock_detector(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["baseline_present"] and body["schema_present"] and body["validator_present"]
    assert body["detector"]["status"] == "mock" and body["detector"]["mock"] is True
    assert body["status"] == "degraded" and any("MOCK" in p for p in body["problems"])


def test_health_when_engine_not_configured(client, set_detector):
    set_detector("")
    body = client.get("/api/health").json()
    assert body["detector"]["status"] == "not_configured"
    assert "CCT_DETECTOR" in body["detector"]["error"]


# --- releases ----------------------------------------------------------------------------

def test_release_discovery(client):
    rels = {r["name"]: r for r in client.get("/api/releases").json()}
    assert {"baseline", "other", "norna", "partial", "envelope-E07"} <= set(rels)
    assert rels["norna"]["has_rna"] is False and rels["norna"]["missing_required"] == []
    assert rels["partial"]["missing_required"] == ["survival.tsv"] and rels["partial"]["comparable"]
    assert rels["envelope-E07"]["origin"] == "envelope"
    detail = client.get("/api/releases/baseline").json()
    assert all(len(f["sha256"]) == 64 for f in detail["provenance"]["files"])


def test_unknown_release_404(client):
    r = client.post("/api/compare", json={"release_a": "baseline", "release_b": "nope"})
    assert r.status_code == 404 and "baseline" in r.json()["detail"]
    assert client.get("/api/releases/nope").status_code == 404


# --- request validation -----------------------------------------------------------------

@pytest.mark.parametrize("payload", [{}, {"release_a": "baseline"}, {"release_a": "../../etc", "release_b": "baseline"},
                                     {"release_a": 5, "release_b": None}, {"release_a": "", "release_b": "baseline"}])
def test_invalid_json_bodies_422(client, payload):
    r = client.post("/api/compare", json=payload)
    assert r.status_code == 422 and "detail" in r.json()
    assert client.get("/api/health").status_code == 200


def test_malformed_body_422(client):
    r = client.post("/api/compare", content="not json", headers={"content-type": "application/json"})
    assert r.status_code == 422


# --- comparison flow ----------------------------------------------------------------------

def test_mock_run_is_labelled_everywhere(client, env):
    rec = _run(client)
    assert rec["status"] == "completed" and rec["detector"]["mock"] is True
    doc = client.get(f"/api/runs/{rec['run_id']}/findings").json()
    assert doc["producer"]["mock"] is True and "MOCK" in doc["producer"]["engine"]
    assert "MOCK" in doc["findings"][0]["summary"]
    assert doc["verdict"] == "Insufficient Evidence"
    # files on disk
    d = env / "outputs" / "runs" / rec["run_id"]
    assert (d / "run.json").is_file() and (d / "findings.json").is_file() and (d / "engine_output.json").is_file()


def test_async_run_then_poll(client):
    r = client.post("/api/compare", json={"release_a": "baseline", "release_b": "other"})
    assert r.status_code == 202
    rid = r.json()["run_id"]
    assert r.json()["status"] in ("pending", "running", "completed")
    for _ in range(200):
        rec = client.get(f"/api/runs/{rid}").json()
        if rec["status"] in ("completed", "failed"):
            break
    assert rec["status"] == "completed" and rec["progress"]
    runs = client.get("/api/runs").json()["runs"]
    assert runs[0]["run_id"] == rid


def test_engine_results_pass_through_and_validate(client, set_detector, env):
    from tests import fake_engines
    fake_engines.CALLS.clear()
    set_detector("tests.fake_engines:full_engine")
    rec = _run(client)
    assert rec["status"] == "completed", rec["error"]
    call = fake_engines.CALLS[0]
    assert call["a"].endswith("raw") and call["b"].endswith("other") and call["names"] == ("baseline", "other")
    assert any("fake engine: working" in p for p in rec["progress"])
    doc = client.get(f"/api/runs/{rec['run_id']}/findings").json()
    assert doc["format_version"] == "0.2" and doc["producer"]["track"] == "cohort-firewall"
    assert doc["findings"] == [fake_engines.VALID_FINDING]  # untouched
    assert doc["analyses"][0]["status"] == "changed" and doc["repairs"][0]["id"] == "R1" and doc["verdict"] == "Blocked"
    assert {r["name"] for r in doc["data"]["releases"]} == {"baseline", "other"}
    # official validator on the exact file served
    path = env / "outputs" / "runs" / rec["run_id"] / "findings.json"
    proc = subprocess.run([sys.executable, str(REPO / "format" / "validate.py"), str(path)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # summary metrics are tallied from the engine's findings
    m = rec["summary"]["metrics"]
    assert m["total_findings"] == 1 and m["sample_swaps"] == 1 and m["samples_in_swaps"] == 1
    assert rec["summary"]["human_review_required"] is True


def test_minimal_engine_positional_signature_and_file_output(client, set_detector):
    set_detector("tests.fake_engines:minimal_engine")
    rec = _run(client)
    assert rec["status"] == "completed", rec["error"]
    doc = client.get(f"/api/runs/{rec['run_id']}/findings").json()
    assert doc["findings"] == [] and "verdict" not in doc
    assert any("no 'analyses'" in n for n in rec["summary"]["notes"])


def test_numpy_values_are_serialised(client, set_detector):
    set_detector("tests.fake_engines:numpy_engine")
    rec = _run(client)
    assert rec["status"] == "completed", rec["error"]
    doc = client.get(f"/api/runs/{rec['run_id']}/findings").json()
    assert doc["analyses"][0]["before"] == {"mean": 1.5, "n": 3}


def test_file_path_detector_spec(client, set_detector):
    set_detector(str(REPO / "tests" / "fake_engines.py") + ":full_engine")
    assert client.get("/api/health").json()["detector"]["status"] == "configured"
    assert _run(client)["status"] == "completed"


# --- error handling -----------------------------------------------------------------------

def test_compare_without_engine_is_503(client, set_detector):
    set_detector("")
    r = client.post("/api/compare", json={"release_a": "baseline", "release_b": "other"})
    assert r.status_code == 503 and "CCT_DETECTOR" in r.json()["detail"]


@pytest.mark.parametrize("engine,needle", [
    ("tests.fake_engines:crashing_engine", "exploded"),
    ("tests.fake_engines:invalid_output_engine", "validator"),
    ("tests.fake_engines:not_a_dict_engine", "requires a dict"),
])
def test_engine_failures_marked_failed(client, set_detector, env, engine, needle):
    set_detector(engine)
    rec = _run(client)
    assert rec["status"] == "failed" and rec["findings_available"] is False
    assert needle.lower() in rec["error"].lower()
    assert client.get(f"/api/runs/{rec['run_id']}/findings").status_code == 409
    d = env / "outputs" / "runs" / rec["run_id"]
    assert not (d / "findings.json").exists()
    if "invalid_output" in engine:
        assert (d / "findings.invalid.json").is_file() and rec["validation"]["valid"] is False
        assert any("NOPE" in e for e in rec["validation"]["errors"])


def test_bad_import_specs_are_503(client, set_detector):
    for spec in ("tests.no_such_module:fn", "tests.fake_engines:no_such_fn", "garbage", "missing/file.py:fn"):
        set_detector(spec)
        r = client.post("/api/compare", json={"release_a": "baseline", "release_b": "other"})
        assert r.status_code == 503, spec
        assert client.get("/api/health").json()["detector"]["status"] == "error"


def test_bad_verdict_is_dropped_not_fatal(client, set_detector):
    set_detector("tests.fake_engines:bad_verdict_engine")
    rec = _run(client)
    assert rec["status"] == "completed"
    assert any("not an allowed value" in n for n in rec["summary"]["notes"])


def test_unknown_run_404(client):
    assert client.get("/api/runs/unknown").status_code == 404
    assert client.get("/api/runs/unknown/findings").status_code == 404


# --- download -----------------------------------------------------------------------------

def test_download_is_exact_bytes(client, env):
    rec = _run(client)
    r = client.get(f"/api/runs/{rec['run_id']}/findings?download=true")
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment")
    assert r.content == (env / "outputs" / "runs" / rec["run_id"] / "findings.json").read_bytes()


# --- frontend <-> backend -----------------------------------------------------------------

def test_frontend_client_talks_to_api(client):
    sys.path.insert(0, str(REPO / "frontend"))
    import api_client
    api = api_client.ApiClient("http://testserver", session=client)
    assert api.health()["detector"]["status"] == "mock"
    assert any(r["name"] == "baseline" for r in api.releases())
    rec = api.compare("baseline", "other", wait=True)
    doc, raw = api.findings(rec["run_id"])
    assert json.loads(raw) == doc
    with pytest.raises(api_client.ApiError) as ei:
        api.run("nope")
    assert ei.value.status == 404


# --- uploads ------------------------------------------------------------------------------

def test_upload_zip_and_rejections(client, env):
    folder = env / "data" / "tcga-brca" / "releases" / "other"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for f in folder.iterdir():
            z.write(f, f"inner/{f.name}")
        z.writestr("inner/CHANGES.json", "{}")  # an answer key is skipped, never stored
    r = client.post("/api/releases/upload", data={"name": "up1"}, files=[("files", ("rel.zip", buf.getvalue(), "application/zip"))])
    assert r.status_code == 201 and r.json()["name"] == "upload-up1"
    assert not (env / "outputs" / "uploads" / "up1" / "CHANGES.json").exists()
    assert _run(client, "baseline", "upload-up1")["status"] == "completed"
    evil = io.BytesIO()
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../../clinical.tsv", "a\tb\n")
    assert client.post("/api/releases/upload", data={"name": "evil"},
                       files=[("files", ("e.zip", evil.getvalue(), "application/zip"))]).status_code == 400
    assert client.post("/api/releases/upload", data={"name": "bad"},
                       files=[("files", ("notes.txt", b"hi\tthere\n", "text/plain"))]).status_code == 422
    assert client.post("/api/releases/upload", data={"name": "../x"},
                       files=[("files", ("clinical.tsv", b"sampleID\tx\n", "text/plain"))]).status_code == 422
    assert client.post("/api/releases/upload", data={"name": "up1"},
                       files=[("files", ("clinical.tsv", b"sampleID\tx\n", "text/plain"))]).status_code == 409
