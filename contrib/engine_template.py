"""Copy-paste skeleton for the detection teammate: the function the API calls.

Suggested location: detection/engine.py (then the API finds it with no configuration).
Any other location works with  CCT_DETECTOR="your.module:analyze_releases"  or
CCT_DETECTOR="path/to/file.py:analyze_releases".

Keep the signature; fill in the body with the team's real comparison logic.
"""
from __future__ import annotations

import json
from pathlib import Path


def analyze_releases(release_a: str, release_b: str, output_path: str, *,
                     release_names: tuple[str, str] | None = None, progress=None) -> dict:
    """Compare two release folders and return findings in shared-format v0.2 shape.

    release_a / release_b : folder paths. Files that may be present:
        clinical.tsv, survival.tsv, mutation_gene_level.tsv.gz, protein_rppa.tsv.gz,
        copy_number_gistic.tsv.gz, rna_hiseq.tsv.gz (optional; absent in the judged release)
    output_path           : write your raw JSON here if you like (kept in the run folder).
    release_names         : (name_a, name_b) to put in evidence pointers' "release" field.
    progress              : call progress("message") to show live progress in the dashboard.

    Return a dict with at least "findings". "analyses", "repairs" and "verdict" are optional but
    the dashboard shows them when present. Raise an exception if the comparison cannot be done.
    """
    a, b = Path(release_a), Path(release_b)
    name_a, name_b = release_names or (a.name, b.name)
    if progress:
        progress(f"Comparing {name_a} with {name_b}")

    # ----- team detection logic goes here -----------------------------------------------
    findings: list[dict] = []
    # Example of one well-formed finding (delete; shown for the field names only):
    # findings.append({
    #     "id": "F01", "kind": "sample_swap",            # kinds: sample_swap, duplicate, missing_data,
    #     "summary": "protein_rppa.tsv.gz: ...",         # membership_change, label_conflict, join_inflation,
    #     "severity": "high", "confidence": "high",      # unlinked_record, claim_check, other
    #     "evidence": [{"kind": "sample", "id": "TCGA-XX-XXXX-01", "release": name_b, "file": "protein_rppa.tsv.gz",
    #                   "note": "profile equals TCGA-YY-YYYY-01 in release A"}],
    #     "affects_analyses": ["A1"], "not_affected_analyses": ["A2"],
    #     "limitation": "...", "needs_human_review": True,
    # })
    analyses: list[dict] = [
        # {"id": "A1", "status": "changed", "before": {...}, "after": {...}},   # status: unchanged | changed | not_rerun
        # {"id": "A2", "status": "not_rerun"},
    ]
    repairs: list[dict] = [
        # {"id": "R01", "action": "exclude", "targets": [{"kind": "sample", "id": "..."}],
        #  "justification": "...", "addresses": ["F01"]},   # action: exclude | relabel | restore_from_previous_release | flag_for_review | other
    ]
    verdict = "Insufficient Evidence"  # Ready | Conditional | Blocked | Insufficient Evidence
    # -------------------------------------------------------------------------------------

    result = {"findings": findings, "analyses": analyses, "repairs": repairs, "verdict": verdict}
    Path(output_path).write_text(json.dumps(result, indent=2, default=str))
    return result
