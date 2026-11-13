"""MOCK detector for isolated infrastructure testing. It does NOT look at the data.

Enable with  CCT_DETECTOR=mock .  Every output is labelled as mock in three places: the run
record (`detector.mock = true`), the findings document (`producer.engine = "MOCK (no detection
performed)"`) and the dashboard banner. The single finding it emits says so in its summary.
Never use it for a demo or a submission.

It also documents the adapter contract: same signature and return shape a real engine must have.
"""
from __future__ import annotations

import json
from pathlib import Path

ENGINE_NAME = "MOCK (no detection performed)"


def analyze_releases(release_a: str, release_b: str, output_path: str, *, release_names=None, progress=None) -> dict:
    name_a, name_b = release_names or (Path(release_a).name, Path(release_b).name)
    if progress:
        progress("MOCK detector: no comparison is performed")
    files_b = sorted(p.name for p in Path(release_b).iterdir()) if Path(release_b).is_dir() else []
    doc = {
        "findings": [{
            "id": "MOCK-1",
            "kind": "other",
            "summary": (f"MOCK RESULT: no detection was performed. The pipeline reached the detector with releases "
                        f"'{name_a}' and '{name_b}'. Connect the team engine via CCT_DETECTOR for real findings."),
            "severity": "none",
            "confidence": "low",
            "evidence": [{"kind": "release", "id": name_b, "note": f"files seen: {', '.join(files_b) or 'none'}"}],
            "affects_analyses": [],
            "not_affected_analyses": [],
            "limitation": "Mock detector: nothing was compared.",
            "needs_human_review": True,
        }],
        "analyses": [{"id": "A1", "status": "not_rerun"}, {"id": "A2", "status": "not_rerun"}],
        "repairs": [],
        "verdict": "Insufficient Evidence",
    }
    Path(output_path).write_text(json.dumps(doc, indent=2))
    return doc
