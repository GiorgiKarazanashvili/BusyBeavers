"""Fast comparison: skip files whose bytes are identical in both releases.

Identical bytes means identical content, so such a file cannot contain a change and does not need
to be loaded or fingerprinted. Only files that differ (plus the two analysis inputs, if any input
differs) are loaded. Results are the same as loading everything, just faster.
"""
import hashlib
from functools import lru_cache
from pathlib import Path

from .diff import diff_releases
from .impact import ANALYSES, impact
from .load import load_release

INPUT_STEMS = {"clinical", "protein_rppa"}                     # files the analyses read
OPTIONAL_STEMS = {"rna_hiseq"}                                  # envelopes ship without RNA: absence is expected
ANALYSIS_INPUTS = {"A1": {"clinical", "protein_rppa"}, "A2": {"clinical"}}


@lru_cache(maxsize=None)
def _sha(path, size, mtime):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(d):
    return {p.name.split(".")[0]: p for p in Path(d).glob("*.tsv*")}


def changed_stems(dir_a, dir_b):
    fa, fb = _files(dir_a), _files(dir_b)
    out = set()
    for s in set(fa) | set(fb):
        if s not in fa or s not in fb:
            if s not in OPTIONAL_STEMS:
                out.add(s)
            continue
        sa, sb = fa[s].stat(), fb[s].stat()
        if _sha(str(fa[s]), sa.st_size, sa.st_mtime_ns) != _sha(str(fb[s]), sb.st_size, sb.st_mtime_ns):
            out.add(s)
    return out


def compare(dir_a, dir_b):
    """Return (A, B, raw_findings, impact). A and B hold only the files that were loaded."""
    changed = changed_stems(dir_a, dir_b)
    need = set(changed)
    if changed & INPUT_STEMS:
        need |= INPUT_STEMS                                    # slices need both inputs
    A, B = load_release(dir_a, only=need), load_release(dir_b, only=need)
    raw = diff_releases(A, B)
    if changed & INPUT_STEMS:
        imp = impact(A, B)
    else:
        imp = {k: dict(affected=False, sample_ids=[],
                       reason=f"its input files ({', '.join(sorted(ANALYSIS_INPUTS[k]))}) are byte-identical between releases ({spec['reads']})")
               for k, spec in ANALYSES.items()}
    return A, B, raw, imp