"""Thin HTTP client the Streamlit app uses. The UI never calls detection code directly.

Optional endpoints (fixes, Q&A, triage) return None from the client when the backend answers 404/405,
so the dashboard keeps working against an API that has not implemented them yet.
"""
from __future__ import annotations

import json
import os
from typing import Any

import requests

DEFAULT_URL = os.environ.get("CCT_API_URL", "http://127.0.0.1:8000")
NOT_IMPLEMENTED = (404, 405, 501)


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.message, self.status = message, status


class ApiClient:
    def __init__(self, base_url: str = DEFAULT_URL, session: Any = None, timeout: float = 30):
        self.base = base_url.rstrip("/")
        self.s = session or requests.Session()
        self.timeout = timeout

    def _call(self, method: str, path: str, **kw):
        try:
            if isinstance(self.s, requests.Session):
                kw.setdefault("timeout", self.timeout)
            r = getattr(self.s, method)(self.base + path, **kw)
        except requests.ConnectionError as e:
            raise ApiError(f"Cannot reach the API at {self.base}. Is `uvicorn backend.main:app` running?") from e
        except requests.Timeout as e:
            raise ApiError(f"The API at {self.base} did not answer in time.") from e
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            raise ApiError(str(detail), r.status_code)
        return r

    def _optional(self, method: str, path: str, **kw):
        """Like _call, but None when the endpoint does not exist on this backend."""
        try:
            return self._call(method, path, **kw).json()
        except ApiError as e:
            if e.status in NOT_IMPLEMENTED:
                return None
            raise

    # ---- core
    def health(self) -> dict:
        return self._call("get", "/api/health").json()

    def releases(self) -> list[dict]:
        return self._call("get", "/api/releases").json()

    def release_detail(self, name: str) -> dict:
        return self._call("get", f"/api/releases/{name}").json()

    def upload(self, name: str, files: list[tuple[str, bytes]]) -> dict:
        payload = [("files", (fname, data, "application/octet-stream")) for fname, data in files]
        return self._call("post", "/api/releases/upload", data={"name": name}, files=payload).json()

    def compare(self, a: str, b: str, wait: bool = False) -> dict:
        return self._call("post", "/api/compare", json={"release_a": a, "release_b": b, "wait": wait}).json()

    def runs(self) -> list[dict]:
        return self._call("get", "/api/runs").json()["runs"]

    def run(self, run_id: str) -> dict:
        return self._call("get", f"/api/runs/{run_id}").json()

    def findings_bytes(self, run_id: str) -> bytes:
        """Exact bytes of the validated findings.json, as written by the backend."""
        return self._call("get", f"/api/runs/{run_id}/findings").content

    def findings(self, run_id: str) -> tuple[dict, bytes]:
        raw = self.findings_bytes(run_id)
        return json.loads(raw), raw

    # ---- optional (see CONTRACT.md)
    def triage(self, run_id: str) -> dict | None:
        return self._optional("get", f"/api/runs/{run_id}/triage")

    def fixes(self, run_id: str) -> list[dict] | None:
        """Fixes applied to this run, or None when the backend has no fix endpoint yet."""
        res = self._optional("get", f"/api/runs/{run_id}/fixes")
        return None if res is None else res.get("fixes", [])

    def apply_fix(self, run_id: str, fix: dict) -> dict:
        return self._call("post", f"/api/runs/{run_id}/fixes", json=fix).json()

    def undo_fix(self, run_id: str, fix_id: str) -> dict:
        return self._call("delete", f"/api/runs/{run_id}/fixes/{fix_id}").json()

    def qa_chips(self) -> dict | None:
        """{"chips": [{"id", "label"}], "free_text_available": bool}, or None when the backend has no Q&A."""
        return self._optional("get", "/api/qa/chips")

    def ask(self, run_id: str, question: str = "", chip: str | None = None) -> dict | None:
        """{"answer", "citations", "source", ["reason"]} from detection/qa.py, or None without the endpoint.
        Typed questions may go to a local model, so this call waits longer than the others."""
        kw = {"timeout": max(self.timeout, 150)} if isinstance(self.s, requests.Session) else {}
        return self._optional("post", f"/api/runs/{run_id}/ask", json={"question": question, "chip": chip}, **kw)
