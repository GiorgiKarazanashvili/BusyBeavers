"""The ONLY bridge between the API and the team's detection engine.

No detection, analysis or repair logic lives in the backend. The adapter locates the engine,
calls it with two release folders, and hands its result to report_export for packaging and
official schema validation.

ENGINE CONTRACT (what the detection teammate implements)
--------------------------------------------------------
    def analyze_releases(release_a: str, release_b: str, output_path: str) -> dict

    release_a, release_b  absolute folder paths. Each holds clinical.tsv, survival.tsv,
                          mutation_gene_level.tsv.gz, protein_rppa.tsv.gz, copy_number_gistic.tsv.gz
                          and maybe rna_hiseq.tsv.gz. The same ids are NOT guaranteed; RNA may be absent.
    output_path           a path inside the run folder where the engine may write its own JSON
                          (optional; kept for debugging). If the function returns None, the adapter
                          reads this file instead.
    returns               a dict in shared-format v0.2 shape. Required: "findings" (list of finding
                          objects). Optional: "analyses", "repairs", "verdict", "question", "producer",
                          "decisions". A complete v0.2 document is accepted as-is.
    on failure            raise an exception. The run is marked failed with the message.

    Optional keyword arguments, passed only if the signature accepts them (or **kwargs):
        release_names=(name_a, name_b)  display names to use in evidence pointers
        progress=callable(str)          progress lines shown live in the dashboard

HOW THE ENGINE IS FOUND (first match wins)
------------------------------------------
    1. CCT_DETECTOR="package.module:function"      importable from the repository root
       CCT_DETECTOR="path/to/engine.py:function"   a file path, relative to the repo root or absolute
       CCT_DETECTOR="mock"                         the labelled mock (isolated testing only)
    2. Default candidates, tried in order when CCT_DETECTOR is unset:
           detection.engine:analyze_releases
           detection:analyze_releases
           detector.engine:analyze_releases
       so a teammate who adds detection/engine.py with that function needs no configuration.
    3. Otherwise the detector is "not configured": /api/health says so and /api/compare answers 503.

Nothing is ever substituted for a missing or failing engine.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from backend import config

DEFAULT_CANDIDATES = ("detection.engine:analyze_releases", "detection:analyze_releases",
                      "detector.engine:analyze_releases")
MOCK_SPEC = "mock"


class DetectorError(Exception):
    """Engine could not be loaded, crashed, or returned something unusable."""


class DetectorNotConfigured(DetectorError):
    """No engine is configured or auto-discoverable."""


@dataclass
class DetectorInfo:
    name: str
    spec: str
    source: str  # env | auto | mock
    mock: bool = False
    tried: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _import_spec(spec: str) -> Callable:
    if ":" not in spec:
        raise DetectorError(f"Detector spec must look like 'package.module:function' or 'file.py:function', got {spec!r}")
    target, func_name = spec.rsplit(":", 1)
    root = str(config.REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    if target.endswith(".py"):
        path = Path(target)
        if not path.is_absolute():
            path = config.REPO_ROOT / path
        if not path.is_file():
            raise DetectorError(f"Detector file not found: {path}")
        mod_spec = importlib.util.spec_from_file_location(f"cct_engine_{path.stem}", path)
        mod = importlib.util.module_from_spec(mod_spec)  # type: ignore[arg-type]
        try:
            mod_spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except Exception as e:
            raise DetectorError(f"Could not load detector file {path}: {type(e).__name__}: {e}") from e
    else:
        try:
            mod = importlib.import_module(target)
        except ModuleNotFoundError as e:
            if e.name and (target == e.name or target.startswith(e.name + ".")):
                raise DetectorError(f"Detector module '{target}' not found (importable from {root}?)") from e
            raise DetectorError(f"Detector module '{target}' failed to import: {type(e).__name__}: {e}") from e
        except Exception as e:
            raise DetectorError(f"Detector module '{target}' failed to import: {type(e).__name__}: {e}") from e
    fn = getattr(mod, func_name, None)
    if not callable(fn):
        raise DetectorError(f"'{func_name}' is not a callable in '{target}'")
    return fn


def resolve(spec: str | None = None) -> tuple[Callable, DetectorInfo]:
    """Find the engine. Raises DetectorNotConfigured / DetectorError with a precise reason."""
    spec = (config.DETECTOR_SPEC if spec is None else spec).strip()
    if spec == MOCK_SPEC:
        from backend.services import mock_detector
        return mock_detector.analyze_releases, DetectorInfo(name=mock_detector.ENGINE_NAME, spec=spec, source="mock", mock=True)
    if spec:
        return _import_spec(spec), DetectorInfo(name=spec, spec=spec, source="env")
    tried = []
    for cand in DEFAULT_CANDIDATES:
        try:
            return _import_spec(cand), DetectorInfo(name=cand, spec=cand, source="auto", tried=tried)
        except DetectorError as e:
            tried.append(f"{cand}: {e}")
    raise DetectorNotConfigured(
        "No detection engine is configured. Set CCT_DETECTOR=\"package.module:function\" (or \"path/engine.py:function\"), "
        "or add detection/engine.py exposing analyze_releases(release_a, release_b, output_path). "
        "For isolated API testing only, CCT_DETECTOR=mock. Tried: " + "; ".join(tried))


def describe() -> dict:
    """Health-check view: configured | auto | mock | not_configured | error."""
    try:
        _, info = resolve()
        d = info.to_dict()
        d["status"] = "mock" if info.mock else ("auto" if info.source == "auto" else "configured")
        return d
    except DetectorNotConfigured as e:
        return {"name": None, "spec": config.DETECTOR_SPEC, "source": None, "mock": False,
                "status": "not_configured", "error": str(e)}
    except DetectorError as e:
        return {"name": config.DETECTOR_SPEC, "spec": config.DETECTOR_SPEC, "source": "env", "mock": False,
                "status": "error", "error": str(e)}


def run(dir_a: Path, dir_b: Path, names: tuple[str, str], work_dir: Path,
        progress: Callable[[str], None] | None = None) -> tuple[dict, DetectorInfo]:
    """Call the engine once. Returns (raw_result, info). Raises DetectorError on any problem."""
    fn, info = resolve()
    out = work_dir / "engine_output.json"
    kwargs: dict = {}
    try:
        params = inspect.signature(fn).parameters
        var_kw = any(p.kind == p.VAR_KEYWORD for p in params.values())
        if "release_names" in params or var_kw:
            kwargs["release_names"] = names
        if "progress" in params or var_kw:
            kwargs["progress"] = progress
    except (TypeError, ValueError):
        pass
    try:
        result = fn(str(dir_a), str(dir_b), str(out), **kwargs)
    except Exception as e:
        raise DetectorError(f"Detection engine '{info.name}' raised {type(e).__name__}: {e}") from e
    if result is None and out.is_file():
        try:
            result = json.loads(out.read_text())
        except json.JSONDecodeError as e:
            raise DetectorError(f"Engine wrote invalid JSON to {out.name}: {e}") from e
    if not isinstance(result, dict):
        raise DetectorError(f"Detection engine '{info.name}' returned {type(result).__name__}; the contract requires a dict")
    if not isinstance(result.get("findings"), list):
        raise DetectorError(f"Detection engine '{info.name}' returned no 'findings' list")
    return result, info
