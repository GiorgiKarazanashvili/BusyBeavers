"""Central configuration: project-relative paths and environment overrides.

Every path is derived from the repository root (the parent of ``backend/``), so the
server works no matter which directory it is started from.

Environment variables (all optional):
  CCT_DETECTOR        where the team's detection engine is: "package.module:function",
                      "path/to/engine.py:function", or "mock" (labelled mock, testing only).
                      Unset: auto-discover detection/engine.py:analyze_releases, else "not configured".
  CCT_OUTPUT_DIR      where run folders are written (default: outputs/)
  CCT_TEAM            producer.team written into findings.json
  CCT_MAX_UPLOAD_MB   per-file upload limit in MB (default 200)
  CCT_API_URL         used by the Streamlit frontend (default http://127.0.0.1:8000)
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "tcga-brca"
BASELINE_DIR = DATA_DIR / "raw"
GENERATED_RELEASES_DIR = DATA_DIR / "releases"
ENVELOPES_OPENED_DIR = REPO_ROOT / "envelopes" / "opened"
SOURCES_CSV = DATA_DIR / "sources.csv"
REFERENCE_ANALYSES_PY = DATA_DIR / "reference_analyses.py"
FORMAT_DIR = REPO_ROOT / "format"
SCHEMA_PATH = FORMAT_DIR / "findings.schema.json"
VALIDATOR_PY = FORMAT_DIR / "validate.py"

OUTPUT_DIR = Path(os.environ.get("CCT_OUTPUT_DIR", REPO_ROOT / "outputs")).resolve()
RUNS_DIR = OUTPUT_DIR / "runs"
UPLOADS_DIR = OUTPUT_DIR / "uploads"

TEAM_NAME = os.environ.get("CCT_TEAM", "Cohort Control Tower team")
PRODUCT_NAME = "Cohort Control Tower"
TRACK = "cohort-firewall"
DATASET_NAME = "TCGA-BRCA (UCSC Xena TCGA hub)"
DETECTOR_SPEC = os.environ.get("CCT_DETECTOR", "").strip()

MAX_UPLOAD_BYTES = int(float(os.environ.get("CCT_MAX_UPLOAD_MB", "200")) * 1024 * 1024)
API_URL = os.environ.get("CCT_API_URL", "http://127.0.0.1:8000")

# The five files every release (including the judges' unseen one) must have, plus optional RNA.
REQUIRED_FILES = (
    "clinical.tsv",
    "survival.tsv",
    "mutation_gene_level.tsv.gz",
    "protein_rppa.tsv.gz",
    "copy_number_gistic.tsv.gz",
)
OPTIONAL_FILES = ("rna_hiseq.tsv.gz",)
KNOWN_FILES = REQUIRED_FILES + OPTIONAL_FILES

# Files never opened by the app: practice answer keys.
FORBIDDEN_FILES = ("CHANGES.json",)


def ensure_dirs() -> None:
    for d in (OUTPUT_DIR, RUNS_DIR, UPLOADS_DIR):
        d.mkdir(parents=True, exist_ok=True)
