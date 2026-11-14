"""Stand-in engines used by the infrastructure tests only (loaded through CCT_DETECTOR)."""
from __future__ import annotations

import json

CALLS: list[dict] = []

VALID_FINDING = {"id": "T1", "kind": "sample_swap", "summary": "test finding from a fake engine", "severity": "high",
                 "confidence": "high", "evidence": [{"kind": "sample", "id": "TCGA-AA-0001-01", "release": "other",
                                                     "file": "protein_rppa.tsv.gz"}],
                 "affects_analyses": ["A1"], "not_affected_analyses": ["A2"], "needs_human_review": True}


def full_engine(release_a, release_b, output_path, *, release_names=None, progress=None):
    """Contract-conformant engine returning findings + analyses + repairs + verdict (all pass-through)."""
    CALLS.append({"a": release_a, "b": release_b, "out": output_path, "names": release_names})
    if progress:
        progress("fake engine: working")
    doc = {"findings": [VALID_FINDING],
           "analyses": [{"id": "A1", "status": "changed", "before": {"difference": 3.05}, "after": {"difference": 3.02}},
                        {"id": "A2", "status": "not_rerun"}],
           "repairs": [{"id": "R1", "action": "exclude", "targets": [VALID_FINDING["evidence"][0]],
                        "justification": "fake", "addresses": ["T1"]}],
           "verdict": "Blocked"}
    with open(output_path, "w") as f:
        json.dump(doc, f)
    return doc


def minimal_engine(release_a, release_b, output_path):
    """Only the required key, positional signature, returns None and writes the file instead."""
    with open(output_path, "w") as f:
        json.dump({"findings": []}, f)
    return None


def numpy_engine(release_a, release_b, output_path):
    import numpy as np
    return {"findings": [dict(VALID_FINDING, severity="low")], "analyses": [{"id": "A1", "status": "unchanged",
            "before": {"mean": np.float64(1.5), "n": np.int64(3)}}], "verdict": "Conditional"}


def crashing_engine(release_a, release_b, output_path):
    raise RuntimeError("engine exploded on purpose")


def invalid_output_engine(release_a, release_b, output_path):
    return {"findings": [{"id": "X", "summary": "bad", "severity": "catastrophic", "confidence": "high",
                          "evidence": [{"kind": "file", "id": "clinical.tsv"}]}],
            "repairs": [{"id": "R", "action": "exclude", "targets": [], "justification": "x", "addresses": ["NOPE"]}]}


def not_a_dict_engine(release_a, release_b, output_path):
    return ["nope"]


def bad_verdict_engine(release_a, release_b, output_path):
    return {"findings": [], "verdict": "Looks fine"}


def fixable_engine(release_a, release_b, output_path, *, release_names=None, progress=None):
    """Findings the dashboard offers easy fixes for: a duplicate (exclude) and a clinical label conflict (relabel)."""
    b = (release_names or ("a", "b"))[1]
    dup = {"id": "F01", "kind": "duplicate", "summary": "identical protein profiles", "severity": "high",
           "confidence": "high", "needs_human_review": True,
           "evidence": [{"kind": "sample", "id": "TCGA-AA-0002-01", "release": b, "file": "protein_rppa.tsv.gz",
                         "note": "protein_rppa.tsv.gz: new id in B; identical profile to TCGA-AA-0003-01"},
                        {"kind": "sample", "id": "TCGA-AA-0003-01", "release": b, "file": "protein_rppa.tsv.gz"}]}
    lab = {"id": "F02", "kind": "label_conflict", "summary": "ER status changed in place", "severity": "high",
           "confidence": "high", "needs_human_review": True,
           "evidence": [{"kind": "sample", "id": "TCGA-AA-0004-01", "release": b, "file": "clinical.tsv",
                         "note": "clinical.tsv: values differ from release A in breast_carcinoma_estrogen_receptor_status"}]}
    doc = {"findings": [dup, lab],
           "repairs": [{"id": "R01", "action": "exclude", "targets": [dup["evidence"][0]], "justification": "dup",
                        "addresses": ["F01"]},
                       {"id": "R02", "action": "flag_for_review", "targets": lab["evidence"], "justification": "check",
                        "addresses": ["F02"]}],
           "verdict": "Conditional"}
    with open(output_path, "w") as f:
        json.dump(doc, f)
    return doc
