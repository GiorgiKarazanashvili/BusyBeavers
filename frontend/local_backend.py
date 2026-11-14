"""Sidecar launcher: start the repository's own FastAPI backend next to the dashboard when no API is reachable.

Normal local use is two terminals (`uvicorn backend.main:app --port 8000` and `streamlit run frontend/app.py`).
On a host that runs a single command (Streamlit Community Cloud), the dashboard calls `ensure_api()` instead:
it tries the configured API URL, and when nothing answers it launches `python -m uvicorn backend.main:app` as a
child process on that same host/port and waits for /api/health. The dashboard then talks to it over HTTP exactly
as it does locally; nothing in backend/ or detection/ changes and no request bypasses the API.

It also fetches the official baseline (without the 64 MB RNA file) and builds the practice release on first
start when they are missing, using the organizers' own scripts.

CCT_MODE (environment variable or Streamlit secret):
  auto     connect to CCT_API_URL, start the sidecar if nothing answers (default)
  http     only connect, never start anything
  sidecar  always make sure the sidecar is running at CCT_API_URL
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA = REPO_ROOT / "data" / "tcga-brca"
RAW = DATA / "raw"
PRACTICE = DATA / "releases" / "practice-B"
REQUIRED = ("clinical.tsv", "survival.tsv", "mutation_gene_level.tsv.gz", "protein_rppa.tsv.gz", "copy_number_gistic.tsv.gz")

_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_log: list[str] = []


def mode() -> str:
    m = os.environ.get("CCT_MODE", "").strip().lower()
    if not m:
        try:
            import streamlit as st
            m = str(st.secrets.get("CCT_MODE", "")).strip().lower()
        except Exception:  # noqa: BLE001  (no secrets file)
            m = ""
    return m if m in ("http", "sidecar", "auto") else "auto"


def baseline_ready() -> bool:
    return all((RAW / f).is_file() for f in REQUIRED)


def practice_ready() -> bool:
    return all((PRACTICE / f).is_file() for f in REQUIRED)


def _run(cmd: list[str], progress=None) -> None:
    proc = subprocess.run([sys.executable, *cmd], cwd=REPO_ROOT, capture_output=True, text=True, timeout=900)
    for line in (proc.stdout + proc.stderr).strip().splitlines()[-12:]:
        _log.append(line)
        if progress:
            progress(line)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n" + (proc.stdout + proc.stderr)[-1500:])


def ensure_data(progress=None) -> dict:
    """Fetch the baseline (no RNA) and build practice-B if missing. Returns what was done."""
    done = {"fetched": False, "built_practice": False}
    with _lock:
        if not baseline_ready():
            if progress:
                progress("Downloading the official baseline (UCSC Xena, 5 files, ~6 MB, checksum-verified)")
            _run(["data/tcga-brca/fetch.py", "--no-rna"], progress)
            done["fetched"] = True
        if not practice_ready():
            if progress:
                progress("Building the practice release B with the organizers' make_release.py")
            _run(["data/tcga-brca/make_release.py"], progress)
            done["built_practice"] = True
    return done


def api_alive(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def ensure_api(url: str, progress=None, wait_s: float = 90) -> str:
    """Make sure the repository's API answers at `url`; start `uvicorn backend.main:app` as a child process if not.

    Returns 'reachable' (something already answered), 'started' (sidecar launched now) or 'running' (our sidecar
    from an earlier page run is still alive). Raises RuntimeError with the uvicorn log when it does not come up."""
    global _proc
    with _lock:
        if api_alive(url):
            return "running" if _proc and _proc.poll() is None else "reachable"
        if _proc and _proc.poll() is None:
            pass  # still booting from a previous rerun: just wait below
        else:
            u = urllib.parse.urlparse(url)
            host, port = u.hostname or "127.0.0.1", u.port or 8000
            if progress:
                progress(f"Starting the Cohort Control Tower API: uvicorn backend.main:app on {host}:{port}")
            env = {**os.environ, "PYTHONPATH": str(REPO_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")}
            logf = open(REPO_ROOT / "outputs" / "sidecar-uvicorn.log", "a") if (REPO_ROOT / "outputs").is_dir() else subprocess.DEVNULL  # noqa: SIM115
            _proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", host, "--port", str(port),
                                      "--log-level", "warning"], cwd=REPO_ROOT, env=env, stdout=logf, stderr=subprocess.STDOUT)
        deadline = time.time() + wait_s
        while time.time() < deadline:
            if api_alive(url):
                _log.append(f"API up at {url} (pid {_proc.pid})")
                return "started"
            if _proc.poll() is not None:
                break
            time.sleep(0.5)
        tail = ""
        p = REPO_ROOT / "outputs" / "sidecar-uvicorn.log"
        if p.is_file():
            tail = "\n".join(p.read_text(errors="replace").splitlines()[-25:])
        raise RuntimeError(f"uvicorn did not answer at {url} (exit code {_proc.poll()}).\n{tail}")


def sidecar_pid() -> int | None:
    return _proc.pid if _proc and _proc.poll() is None else None


def bootstrap_log() -> list[str]:
    return list(_log)
