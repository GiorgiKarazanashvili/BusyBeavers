"""Easy-fix endpoints: apply / list / undo, patched release, impact preview, export (shared format v0.2)."""
from __future__ import annotations

import gzip
import json

import pytest

from tests.conftest import REPO


@pytest.fixture
def run_id(client, set_detector):
    set_detector("tests.fake_engines:fixable_engine")
    r = client.post("/api/compare", json={"release_a": "baseline", "release_b": "norna", "wait": True})
    assert r.status_code == 202 and r.json()["status"] == "completed", r.text
    return r.json()["run_id"]


EXCL = {"finding_id": "F01", "repair_id": "R01", "action": "exclude", "record_id": "TCGA-AA-0002-01",
        "file": "protein_rppa.tsv.gz"}
RELAB = {"finding_id": "F02", "repair_id": "R02", "action": "relabel", "record_id": "TCGA-AA-0004-01",
         "file": "clinical.tsv", "field": "breast_carcinoma_estrogen_receptor_status", "new_value": "Negative"}


def test_health_advertises_fixes(client):
    assert client.get("/api/health").json()["features"]["fixes"] is True


def test_empty_list_then_apply_and_undo(client, run_id):
    assert client.get(f"/api/runs/{run_id}/fixes").json()["fixes"] == []
    r = client.post(f"/api/runs/{run_id}/fixes", json=EXCL)
    assert r.status_code == 201, r.text
    fx = r.json()
    assert fx["status"] == "applied" and fx["fix_id"] == "X001"
    r2 = client.post(f"/api/runs/{run_id}/fixes", json=RELAB).json()
    assert r2["old_value"] == "Positive" and r2["new_value"] == "Negative"
    assert len(client.get(f"/api/runs/{run_id}/fixes").json()["fixes"]) == 2
    assert client.delete(f"/api/runs/{run_id}/fixes/X001").json()["status"] == "undone"
    assert [x["fix_id"] for x in client.get(f"/api/runs/{run_id}/fixes").json()["fixes"]] == ["X002"]
    log = client.get(f"/api/runs/{run_id}/fixes?include_undone=true").json()["fixes"]
    assert [x["status"] for x in log] == ["undone", "applied"]
    assert client.delete(f"/api/runs/{run_id}/fixes/X001").status_code == 409
    assert client.delete(f"/api/runs/{run_id}/fixes/X999").status_code == 404
    # after undo the same fix can be applied again
    assert client.post(f"/api/runs/{run_id}/fixes", json=EXCL).status_code == 201


@pytest.mark.parametrize("change,status", [
    ({"finding_id": "F99"}, 404),
    ({"record_id": "TCGA-AA-0005-01"}, 422),            # not in the finding's evidence
    ({"repair_id": "R02"}, 422),                         # repair does not address F01
    ({"repair_id": "R77"}, 404),
    ({"file": "../../etc/passwd"}, 422),
    ({"action": "delete"}, 422),
])
def test_bad_fix_requests(client, run_id, change, status):
    assert client.post(f"/api/runs/{run_id}/fixes", json={**EXCL, **change}).status_code == status


@pytest.mark.parametrize("change", [{"field": "sampleID"}, {"field": "no_such_column"}, {"new_value": "Positive"},
                                    {"new_value": "a\tb"}, {"new_value": ""}, {"file": "protein_rppa.tsv.gz"}])
def test_bad_relabels(client, run_id, change):
    assert client.post(f"/api/runs/{run_id}/fixes", json={**RELAB, **change}).status_code == 422


def test_duplicate_fix_conflicts(client, run_id):
    assert client.post(f"/api/runs/{run_id}/fixes", json=EXCL).status_code == 201
    assert client.post(f"/api/runs/{run_id}/fixes", json=EXCL).status_code == 409


def test_unknown_run(client):
    assert client.get("/api/runs/nope/fixes").status_code == 404
    assert client.post("/api/runs/nope/fixes", json=EXCL).status_code == 404


def _zip(client, run_id, mode):
    import io, zipfile
    r = client.get(f"/api/runs/{run_id}/fixes/dataset?mode={mode}")
    return r, (zipfile.ZipFile(io.BytesIO(r.content)) if r.status_code == 200 else None)


def test_dataset_modes(client, run_id, env):
    src = env / "data" / "tcga-brca" / "releases" / "norna"
    assert _zip(client, run_id, "user")[0].status_code == 409            # nothing applied yet
    assert _zip(client, run_id, "nope")[0].status_code == 422

    # easy: the engine's exclude repair (R01 -> TCGA-AA-0002-01 in protein), no clicks needed
    r, z = _zip(client, run_id, "easy")
    assert r.status_code == 200 and "norna-easy-fixed.zip" in r.headers["content-disposition"]
    with z.open("norna-easy-fixed/protein_rppa.tsv.gz") as f:
        header = gzip.decompress(f.read()).decode().splitlines()[0]
    assert "TCGA-AA-0002-01" not in header and "TCGA-AA-0003-01" in header
    assert z.read("norna-easy-fixed/clinical.tsv") == (src / "clinical.tsv").read_bytes()

    # user: only what the person applied (here a relabel and removing 0003, which the engine did not suggest)
    client.post(f"/api/runs/{run_id}/fixes", json=RELAB)
    client.post(f"/api/runs/{run_id}/fixes", json={**EXCL, "record_id": "TCGA-AA-0003-01"})
    r, z = _zip(client, run_id, "user")
    assert "TCGA-AA-0004-01\tTCGA-AA-0004\tNegative" in z.read("norna-user-fixed/clinical.tsv").decode()
    with z.open("norna-user-fixed/protein_rppa.tsv.gz") as f:
        header = gzip.decompress(f.read()).decode().splitlines()[0]
    assert "TCGA-AA-0003-01" not in header and "TCGA-AA-0002-01" in header
    assert "TCGA-AA-0004-01\tTCGA-AA-0004\tPositive" in (src / "clinical.tsv").read_text()  # release B untouched


def test_api_client_roundtrip(client, run_id):
    import sys
    sys.path.insert(0, str(REPO / "frontend"))
    from api_client import ApiClient
    api = ApiClient("http://testserver", session=client)
    assert api.fixes(run_id) == []
    fx = api.apply_fix(run_id, EXCL)
    assert [x["fix_id"] for x in api.fixes(run_id)] == [fx["fix_id"]]
    api.undo_fix(run_id, fx["fix_id"])
    assert api.fixes(run_id) == []
