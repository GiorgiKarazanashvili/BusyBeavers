"""Pydantic request/response models for the API."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

RunStatus = Literal["pending", "running", "completed", "failed"]
RELEASE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$"


class CompareRequest(BaseModel):
    release_a: str = Field(..., description="Baseline release name, e.g. 'baseline'", pattern=RELEASE_PATTERN)
    release_b: str = Field(..., description="Updated release name, e.g. 'practice-B' or 'envelope-E07'", pattern=RELEASE_PATTERN)
    wait: bool = Field(False, description="Block until the run finishes (default: return immediately and poll)")

    @field_validator("release_a", "release_b")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class ReleaseInfo(BaseModel):
    name: str
    origin: str
    location: str
    files: dict[str, bool]
    missing_required: list[str]
    has_rna: bool
    comparable: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    detector: dict[str, Any]
    baseline_present: bool
    releases_found: int
    schema_present: bool
    validator_present: bool
    problems: list[str]
    features: dict[str, bool] = {}


class Validation(BaseModel):
    valid: bool
    errors: list[str] = []
    validator: str = "format/validate.py"


class RunRecord(BaseModel):
    run_id: str
    status: RunStatus
    release_a: str
    release_b: str
    detector: dict[str, Any]
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    progress: list[str] = []
    error: Optional[str] = None
    validation: Optional[Validation] = None
    findings_available: bool = False
    verdict: Optional[str] = None
    summary: Optional[dict[str, Any]] = None


class RunList(BaseModel):
    runs: list[RunRecord]


class FixRequest(BaseModel):
    """One easy fix, as posted by the dashboard (frontend/app.py: relabel_row / exclude_row)."""
    finding_id: str = Field(..., max_length=40)
    repair_id: Optional[str] = Field(None, max_length=40)
    action: Literal["exclude", "relabel"]
    record_id: str = Field(..., min_length=1, max_length=80)
    file: Optional[str] = Field(None, max_length=300)
    field: Optional[str] = Field(None, max_length=200)
    new_value: Optional[str] = Field(None, max_length=200)
    actor: Optional[str] = Field(None, max_length=80, description="Who applied it (role or name); defaults to 'dashboard user'")
