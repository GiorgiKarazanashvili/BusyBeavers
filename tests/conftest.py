"""Fixtures for the infrastructure tests.

Tiny synthetic release folders (correct file names and TSV/TSV.GZ shapes, a handful of rows) so
the API, adapter, run storage and export can be exercised in a second without the real download.
Scientific correctness of any detector is NOT tested here; that is the detection teammates' job.
"""
from __future__ import annotations

import gzip
import importlib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SAMPLES = [f"TCGA-AA-{i:04d}-01" for i in range(1, 6)] + ["TCGA-AA-0001-11"]


def _tsv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    text = "\n".join("\t".join(r) for r in [header, *rows]) + "\n"
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        path.write_text(text)


def make_release(folder: Path, samples: list[str] = SAMPLES, *, with_rna: bool = True,
                 drop: tuple[str, ...] = ()) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    _tsv(folder / "clinical.tsv", ["sampleID", "_PATIENT", "breast_carcinoma_estrogen_receptor_status", "PAM50Call_RNAseq"],
         [[s, s[:12], "Positive", "LumA"] for s in samples])
    _tsv(folder / "survival.tsv", ["sample", "_PATIENT", "OS", "OS.time"], [[s, s[:12], "0", "100"] for s in samples])
    _tsv(folder / "protein_rppa.tsv.gz", ["Sample_description", *samples], [["ERALPHA", *["0.5"] * len(samples)]])
    _tsv(folder / "mutation_gene_level.tsv.gz", ["sample", *samples], [["TP53", *["0"] * len(samples)]])
    _tsv(folder / "copy_number_gistic.tsv.gz", ["Gene Symbol", *samples], [["ERBB2", *["1"] * len(samples)]])
    if with_rna:
        _tsv(folder / "rna_hiseq.tsv.gz", ["sample", *samples], [["ESR1", *["5.5"] * len(samples)]])
    for f in drop:
        (folder / f).unlink(missing_ok=True)
    return folder


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Temporary data tree: baseline + 'other' (same count, one id swapped out) + 'norna' + 'partial'."""
    data = tmp_path / "data" / "tcga-brca"
    base = make_release(data / "raw")
    make_release(data / "releases" / "other", SAMPLES[:-1] + ["TCGA-ZZ-0099-01"], with_rna=False)
    make_release(data / "releases" / "norna", with_rna=False)
    make_release(data / "releases" / "partial", with_rna=False, drop=("survival.tsv",))
    (tmp_path / "envelopes" / "opened" / "E07" / "release").mkdir(parents=True)
    make_release(tmp_path / "envelopes" / "opened" / "E07" / "release", with_rna=False)

    monkeypatch.setenv("CCT_OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("CCT_DETECTOR", "mock")
    from backend import config
    importlib.reload(config)
    monkeypatch.setattr(config, "BASELINE_DIR", base)
    monkeypatch.setattr(config, "GENERATED_RELEASES_DIR", data / "releases")
    monkeypatch.setattr(config, "ENVELOPES_OPENED_DIR", tmp_path / "envelopes" / "opened")
    monkeypatch.setattr(config, "SOURCES_CSV", tmp_path / "no-sources.csv")
    from backend.services import comparison
    comparison._runs.clear()
    return tmp_path


@pytest.fixture
def client(env):
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def set_detector(monkeypatch):
    def _set(spec: str):
        from backend import config
        monkeypatch.setattr(config, "DETECTOR_SPEC", spec)
    return _set
