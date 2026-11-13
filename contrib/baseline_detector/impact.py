"""Reference-analysis registry, dependency mapping and selective reruns.

The analysis logic itself is NOT reimplemented here: ``a1``/``a2`` are imported from the
organizers' data/tcga-brca/reference_analyses.py and called on each release's files.
This module only declares what each analysis depends on, so a finding can be mapped to the
analyses it can (and cannot) affect, and so only affected analyses are rerun.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from backend import config


@dataclass(frozen=True)
class AnalysisSpec:
    id: str
    title: str
    files: tuple[str, ...]
    clinical_columns: tuple[str, ...]  # clinical.tsv columns it reads
    matrix_features: dict  # file -> tuple of features read (None = all)


ANALYSES: dict[str, AnalysisSpec] = {
    "A1": AnalysisSpec(
        id="A1",
        title="ER-alpha protein by clinical ER status",
        files=("clinical.tsv", "protein_rppa.tsv.gz"),
        clinical_columns=("sampleID", "breast_carcinoma_estrogen_receptor_status"),
        matrix_features={"protein_rppa.tsv.gz": ("ERALPHA",)},
    ),
    "A2": AnalysisSpec(
        id="A2",
        title="RNA subtype (PAM50) mix of primary tumors",
        files=("clinical.tsv",),
        clinical_columns=("sampleID", "PAM50Call_RNAseq"),
        matrix_features={},
    ),
}


@lru_cache(maxsize=1)
def reference_module():
    spec = importlib.util.spec_from_file_location("cct_reference_analyses", config.REFERENCE_ANALYSES_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {config.REFERENCE_ANALYSES_PY}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_clinical(folder: Path) -> pd.DataFrame:
    return pd.read_csv(folder / "clinical.tsv", sep="\t", low_memory=False)


def _load_protein(folder: Path) -> pd.DataFrame:
    return pd.read_csv(folder / "protein_rppa.tsv.gz", sep="\t", index_col=0)


def run_analysis(analysis_id: str, folder: Path, exclude: dict[str, set[str]] | None = None) -> dict:
    """Run a reference analysis on a release folder.

    ``exclude`` maps file -> sample ids to drop from that file first (repair preview only;
    the release files on disk are never modified).
    Returns the reference output including ``sample_ids``.
    """
    ref = reference_module()
    exclude = exclude or {}
    spec = ANALYSES[analysis_id]
    for f in spec.files:
        if not (folder / f).is_file():
            raise FileNotFoundError(f"{analysis_id} needs {f}, which is missing from {folder.name}")
    clinical = _load_clinical(folder)
    if "clinical.tsv" in exclude:
        clinical = clinical[~clinical["sampleID"].isin(exclude["clinical.tsv"])]
    if analysis_id == "A1":
        protein = _load_protein(folder)
        drop = [c for c in protein.columns if c in exclude.get("protein_rppa.tsv.gz", set())]
        protein = protein.drop(columns=drop)
        return ref.a1(clinical, protein)
    if analysis_id == "A2":
        return ref.a2(clinical)
    raise KeyError(analysis_id)


def to_builtin(obj):
    """Convert numpy/pandas scalars (e.g. np.float64 from the reference code) to JSON types."""
    if isinstance(obj, dict):
        return {str(k): to_builtin(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_builtin(v) for v in obj]
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            return obj.item()
        except (ValueError, AttributeError):
            pass
    return obj


def summarize(result: dict) -> dict:
    """Drop the long sample list but keep its size, for findings.json before/after blocks."""
    out = {k: v for k, v in result.items() if k != "sample_ids"}
    out["n_ids_listed"] = len(result.get("sample_ids", []))
    return to_builtin(out)


def compare_results(before: dict, after: dict) -> dict:
    """What moved between two runs of the same analysis (numbers and input membership)."""
    b_ids, a_ids = set(before.get("sample_ids", [])), set(after.get("sample_ids", []))
    numeric_changes = {}
    for k, v in before.items():
        if k in ("sample_ids", "inputs", "analysis"):
            continue
        if after.get(k) != v:
            numeric_changes[k] = {"before": v, "after": after.get(k)}
    for k, v in after.items():
        if k not in before and k not in ("sample_ids",):
            numeric_changes[k] = {"before": None, "after": v}
    return to_builtin({
        "inputs_added": sorted(a_ids - b_ids),
        "inputs_removed": sorted(b_ids - a_ids),
        "result_changes": numeric_changes,
        "result_changed": bool(numeric_changes),
        "membership_changed": a_ids != b_ids,
    })
