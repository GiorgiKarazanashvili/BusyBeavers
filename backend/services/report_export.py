"""Package the engine's result as the official findings.json (format v0.2) and validate it.

The engine owns the science: findings, analyses (before/after), repairs, verdict. This module
only adds the envelope the format requires (format_version, producer, data with release
checksums, question), passes everything else through unchanged, and runs the organizers'
format/validate.py. An invalid document is never presented as a successful result.
"""
from __future__ import annotations

import importlib.util
import json
from functools import lru_cache
from pathlib import Path

from backend import config
from backend.services.releases import Release, checksum_entries

QUESTION = ("What changed between release {a} (baseline) and release {b}, which records are affected, "
            "and do those changes make reference analyses A1 or A2 unreliable?")
VERDICTS = ("Ready", "Conditional", "Blocked", "Insufficient Evidence",
            "Proceed", "Fix a problem", "Narrow the question", "Stop")
PASS_THROUGH = ("findings", "analyses", "repairs", "decisions")


def to_builtin(obj):
    """numpy / pandas scalars -> plain JSON types (engines often return np.float64)."""
    if isinstance(obj, dict):
        return {str(k): to_builtin(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_builtin(v) for v in obj]
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            return obj.item()
        except (ValueError, AttributeError, TypeError):
            pass
    return obj


@lru_cache(maxsize=1)
def _validator():
    spec = importlib.util.spec_from_file_location("cct_official_validate", config.VALIDATOR_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {config.VALIDATOR_PY}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def validate_file(path: Path) -> list[str]:
    """Run the organizers' check(): JSON schema + repair/decision references. [] means valid."""
    try:
        return list(_validator().check(str(path)))
    except SystemExit as e:  # validate.py exits if jsonschema is missing
        return [f"validator could not run: {e}"]
    except Exception as e:
        return [f"validator error: {type(e).__name__}: {e}"]


def build_document(raw: dict, rel_a: Release, rel_b: Release, detector_info: dict) -> tuple[dict, list[str]]:
    """Return (document, notes). Notes describe what the app added or could not find."""
    notes: list[str] = []
    producer = {"team": config.TEAM_NAME, "product": config.PRODUCT_NAME, "track": config.TRACK,
                "engine": detector_info.get("name")}
    if detector_info.get("mock"):
        producer["engine"] = "MOCK (no detection performed)"
        producer["mock"] = True
    if isinstance(raw.get("producer"), dict):
        producer["engine_producer"] = raw["producer"]  # keep the engine's own identification
    doc: dict = {
        "format_version": "0.2",
        "producer": producer,
        "data": {"dataset": config.DATASET_NAME,
                 "releases": [{"name": rel_a.name, "role": "A (baseline)", "files": checksum_entries(rel_a)},
                              {"name": rel_b.name, "role": "B (updated)", "files": checksum_entries(rel_b)}]},
        "question": raw.get("question") or QUESTION.format(a=rel_a.name, b=rel_b.name),
    }
    if isinstance(raw.get("data"), dict) and raw["data"].get("releases"):
        doc["data"]["engine_data"] = raw["data"]
    verdict = raw.get("verdict")
    if verdict in VERDICTS:
        doc["verdict"] = verdict
    elif verdict is not None:
        notes.append(f"Engine verdict {verdict!r} is not an allowed value and was omitted.")
    else:
        notes.append("Engine returned no verdict.")
    for key in PASS_THROUGH:
        if key in raw and raw[key] is not None:
            doc[key] = raw[key]
    if "analyses" not in doc:
        notes.append("Engine returned no 'analyses' block (A1/A2 before/after).")
    if "repairs" not in doc:
        notes.append("Engine returned no 'repairs'.")
    return to_builtin(doc), notes


def write_document(doc: dict, path: Path) -> list[str]:
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    return validate_file(path)
