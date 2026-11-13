"""Release discovery, file inventory, checksums and safe uploads.

A *release* is a folder holding some of the TCGA-BRCA files listed in config.KNOWN_FILES.
Releases are discovered (never typed in as raw paths by API clients) from:

  * ``baseline``                     data/tcga-brca/raw/                (official fetch.py output)
  * ``<name>``                       data/tcga-brca/releases/<name>/    (make_release.py output, e.g. practice-B)
  * ``envelope-<id>``                envelopes/opened/<id>/release/     (unseal.py output on judging day)
  * ``upload-<name>``                outputs/uploads/<name>/            (POST /api/releases/upload)

The app never opens CHANGES.json (practice answer key).
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import re
import shutil
import threading
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from backend import config

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
RELEASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$")
SAMPLE_RE = re.compile(r"^TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}-\d{2}$")

_hash_cache: dict[tuple, str] = {}
_hash_lock = threading.Lock()


class ReleaseError(Exception):
    """Raised for user-facing release problems (unknown name, bad upload...)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class Release:
    name: str
    path: Path
    origin: str  # baseline | generated | envelope | upload
    files: dict[str, bool] = field(default_factory=dict)

    @property
    def missing_required(self) -> list[str]:
        return [f for f in config.REQUIRED_FILES if not self.files.get(f)]

    @property
    def has_rna(self) -> bool:
        return bool(self.files.get("rna_hiseq.tsv.gz"))

    def file_path(self, name: str) -> Path:
        return self.path / name

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "origin": self.origin,
            "location": _display_path(self.path),
            "files": {f: bool(self.files.get(f)) for f in config.KNOWN_FILES},
            "missing_required": self.missing_required,
            "has_rna": self.has_rna,
            "comparable": any(self.files.get(f) for f in config.REQUIRED_FILES),
        }


def _display_path(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(config.REPO_ROOT))
    except ValueError:
        return str(p)


def _inventory(path: Path) -> dict[str, bool]:
    return {f: (path / f).is_file() for f in config.KNOWN_FILES}


def _candidate_dirs() -> Iterable[tuple[str, Path, str]]:
    yield "baseline", config.BASELINE_DIR, "baseline"
    if config.GENERATED_RELEASES_DIR.is_dir():
        for d in sorted(config.GENERATED_RELEASES_DIR.iterdir()):
            if d.is_dir() and NAME_RE.match(d.name):
                yield d.name, d, "generated"
    if config.ENVELOPES_OPENED_DIR.is_dir():
        for d in sorted(config.ENVELOPES_OPENED_DIR.iterdir()):
            rel = d / "release"
            if rel.is_dir() and NAME_RE.match(d.name):
                yield f"envelope-{d.name}", rel, "envelope"
    if config.UPLOADS_DIR.is_dir():
        for d in sorted(config.UPLOADS_DIR.iterdir()):
            if d.is_dir() and NAME_RE.match(d.name):
                yield f"upload-{d.name}", d, "upload"


def discover() -> list[Release]:
    out: list[Release] = []
    seen: set[str] = set()
    for name, path, origin in _candidate_dirs():
        if name in seen or not path.is_dir():
            continue
        inv = _inventory(path)
        if not any(inv.values()):
            continue
        seen.add(name)
        out.append(Release(name=name, path=path, origin=origin, files=inv))
    return out


def get_release(name: str) -> Release:
    if not isinstance(name, str) or not RELEASE_ID_RE.match(name):
        raise ReleaseError(f"Invalid release name: {name!r}", 422)
    for r in discover():
        if r.name == name:
            return r
    known = ", ".join(r.name for r in discover()) or "none (run data/tcga-brca/fetch.py first)"
    raise ReleaseError(f"Release '{name}' not found. Available releases: {known}", 404)


# --------------------------------------------------------------------------- checksums

def sha256_file(path: Path) -> str:
    st = path.stat()
    key = ("file", str(path), st.st_size, st.st_mtime_ns)
    with _hash_lock:
        if key in _hash_cache:
            return _hash_cache[key]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    with _hash_lock:
        _hash_cache[key] = digest
    return digest


def sha256_content(path: Path) -> str:
    """Hash of decompressed content (the convention make_release.py uses for generated releases)."""
    if not str(path).endswith(".gz"):
        return sha256_file(path)
    st = path.stat()
    key = ("content", str(path), st.st_size, st.st_mtime_ns)
    with _hash_lock:
        if key in _hash_cache:
            return _hash_cache[key]
    h = hashlib.sha256()
    with gzip.open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    with _hash_lock:
        _hash_cache[key] = digest
    return digest


def official_checksums() -> dict[str, str]:
    if not config.SOURCES_CSV.is_file():
        return {}
    with open(config.SOURCES_CSV, newline="") as f:
        return {row["file"]: row["sha256"] for row in csv.DictReader(f)}


def checksum_entries(release: Release) -> list[dict]:
    """Checksums for findings.json ``data.releases[].files``.

    The baseline uses the as-downloaded file hash (comparable with sources.csv); other releases
    use the decompressed-content hash for .gz files, because gzip bytes differ between systems.
    """
    entries = []
    for f in config.KNOWN_FILES:
        if not release.files.get(f):
            continue
        p = release.file_path(f)
        if release.origin == "baseline" or not f.endswith(".gz"):
            entries.append({"file": f, "sha256": sha256_file(p), "hash_of": "file"})
        else:
            entries.append({"file": f, "sha256": sha256_content(p), "hash_of": "content"})
    return entries


def provenance(release: Release) -> dict:
    """Checksums plus, for every file, whether it matches the organizers' frozen baseline."""
    official = official_checksums()
    files = []
    for e in checksum_entries(release):
        p = release.file_path(e["file"])
        file_hash = e["sha256"] if e["hash_of"] == "file" else sha256_file(p)
        files.append({**e, "bytes": p.stat().st_size,
                      "matches_official_baseline": official.get(e["file"]) == file_hash})
    return {"release": release.name, "files": files}


# --------------------------------------------------------------------------- uploads

def _safe_member_name(member: str) -> str | None:
    """Accept 'clinical.tsv' or 'anyfolder/clinical.tsv'; reject traversal and unknown names."""
    norm = member.replace("\\", "/")
    if norm.startswith("/") or ".." in norm.split("/") or ":" in norm:
        raise ReleaseError(f"Unsafe path in archive: {member!r}", 400)
    base = norm.rsplit("/", 1)[-1]
    if not base or norm.endswith("/"):
        return None  # directory entry
    if base.startswith(".") or base.startswith("__MACOSX") or "__MACOSX/" in norm:
        return None
    return base


def save_upload(name: str, files: list[tuple[str, io.BufferedIOBase]]) -> Release:
    """Store an uploaded release under outputs/uploads/<name>/.

    ``files`` is a list of (filename, binary stream). Either the five/six known files, or a single
    .zip that contains them (one optional top-level folder). Unknown names are rejected.
    """
    if not NAME_RE.match(name or ""):
        raise ReleaseError("Release name must be 1-64 characters: letters, digits, '-', '_' or '.'", 422)
    if not files:
        raise ReleaseError("No files were uploaded.", 422)
    config.ensure_dirs()
    dest = config.UPLOADS_DIR / name
    if dest.exists():
        raise ReleaseError(f"An uploaded release named '{name}' already exists.", 409)
    tmp = config.UPLOADS_DIR / f".tmp-{name}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    try:
        if len(files) == 1 and files[0][0].lower().endswith(".zip"):
            _extract_zip(files[0][1], tmp)
        else:
            for fname, stream in files:
                base = _safe_member_name(fname)
                if base is None:
                    continue
                if base not in config.KNOWN_FILES:
                    raise ReleaseError(
                        f"Unexpected file '{base}'. Allowed: {', '.join(config.KNOWN_FILES)}", 422)
                _copy_limited(stream, tmp / base)
        inv = _inventory(tmp)
        if not any(inv[f] for f in config.REQUIRED_FILES):
            raise ReleaseError("Upload contains none of the expected release files.", 422)
        _sanity_check(tmp)
        tmp.rename(dest)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return get_release(f"upload-{name}")


def _copy_limited(stream, target: Path) -> None:
    if target.exists():
        raise ReleaseError(f"File '{target.name}' supplied twice.", 422)
    written = 0
    with open(target, "wb") as out:
        while True:
            chunk = stream.read(1 << 20)
            if not chunk:
                break
            written += len(chunk)
            if written > config.MAX_UPLOAD_BYTES:
                raise ReleaseError(
                    f"'{target.name}' exceeds the {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.", 413)
            out.write(chunk)


def _extract_zip(stream, dest: Path) -> None:
    raw = io.BytesIO()
    _copy_stream_limited(stream, raw, config.MAX_UPLOAD_BYTES * 2)
    try:
        zf = zipfile.ZipFile(raw)
    except zipfile.BadZipFile as e:
        raise ReleaseError(f"Not a valid zip archive: {e}", 422) from e
    with zf:
        total = 0
        for info in zf.infolist():
            if info.flag_bits & 0x1:
                raise ReleaseError("Encrypted archives are not supported.", 422)
            # reject symlinks (unix mode in external_attr)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ReleaseError(f"Symbolic link in archive: {info.filename!r}", 400)
            base = _safe_member_name(info.filename)
            if base is None:
                continue
            if base in config.FORBIDDEN_FILES:
                continue  # answer keys are skipped, never read
            if base not in config.KNOWN_FILES:
                raise ReleaseError(f"Unexpected file '{base}' in archive. Allowed: {', '.join(config.KNOWN_FILES)}", 422)
            if info.file_size > config.MAX_UPLOAD_BYTES:
                raise ReleaseError(f"'{base}' exceeds the upload size limit.", 413)
            total += info.file_size
            if total > config.MAX_UPLOAD_BYTES * 2:
                raise ReleaseError("Archive content is too large.", 413)
            with zf.open(info) as src:
                _copy_limited(src, dest / base)


def _copy_stream_limited(src, dst, limit: int) -> None:
    n = 0
    while True:
        chunk = src.read(1 << 20)
        if not chunk:
            break
        n += len(chunk)
        if n > limit:
            raise ReleaseError("Upload is too large.", 413)
        dst.write(chunk)
    dst.seek(0)


def _sanity_check(folder: Path) -> None:
    """Make sure each file is readable as (gzipped) tab-separated text with a header."""
    for f in config.KNOWN_FILES:
        p = folder / f
        if not p.is_file():
            continue
        try:
            opener = gzip.open if f.endswith(".gz") else open
            with opener(p, "rt", encoding="utf-8", errors="strict") as fh:
                header = fh.readline()
        except (OSError, UnicodeDecodeError, EOFError) as e:
            raise ReleaseError(f"'{f}' could not be read ({'gzip' if f.endswith('.gz') else 'text'}): {e}", 422) from e
        if "\t" not in header:
            raise ReleaseError(f"'{f}' does not look tab-separated.", 422)
