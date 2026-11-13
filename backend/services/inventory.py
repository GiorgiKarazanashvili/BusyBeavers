"""Lightweight release inventory for the dashboard header: how many sample ids each file lists.

This is bookkeeping about the files (ids in headers / first columns), not detection. All
scientific findings, swaps, duplicates and analysis results come from the detection engine.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.services.releases import Release

ROW_TABLES = {"clinical.tsv": "sampleID", "survival.tsv": "sample"}


def read_sample_ids(path: Path, file: str) -> list[str]:
    """Sample ids as listed in a file: first column for row tables, header for matrices."""
    if file in ROW_TABLES:
        df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, usecols=[0])
        return [str(x) for x in df.iloc[:, 0]]
    df = pd.read_csv(path, sep="\t", dtype=str, nrows=0, index_col=0)
    return [str(c) for c in df.columns]


def patient_of(sample_id: str) -> str:
    """TCGA convention: the first 12 characters of a sample barcode identify the patient."""
    return sample_id[:12]


def inventory(rel: Release) -> dict:
    per_file: dict[str, dict] = {}
    all_ids: set[str] = set()
    for f, present in rel.files.items():
        if not present:
            continue
        try:
            ids = set(read_sample_ids(rel.file_path(f), f))
        except Exception as e:  # unreadable file is reported, not hidden
            per_file[f] = {"error": f"{type(e).__name__}: {e}", "ids": set()}
            continue
        per_file[f] = {"samples": len(ids), "ids": ids}
        all_ids |= ids
    return {"per_file": per_file, "ids": all_ids,
            "patients": len({patient_of(i) for i in all_ids})}


def membership_table(inv_a: dict, inv_b: dict) -> dict[str, dict]:
    """Per-file id counts and raw added/removed id counts between two inventories."""
    out = {}
    for f in sorted(set(inv_a["per_file"]) | set(inv_b["per_file"])):
        a, b = inv_a["per_file"].get(f), inv_b["per_file"].get(f)
        sa, sb = (a or {}).get("ids", set()), (b or {}).get("ids", set())
        both = bool(a and b and "error" not in a and "error" not in b)
        out[f] = {"samples_a": (a or {}).get("samples"), "samples_b": (b or {}).get("samples"),
                  "added": len(sb - sa) if both else None, "removed": len(sa - sb) if both else None,
                  "count_equal_membership_differs": both and len(sa) == len(sb) and sa != sb,
                  "error": (a or {}).get("error") or (b or {}).get("error")}
    return out
