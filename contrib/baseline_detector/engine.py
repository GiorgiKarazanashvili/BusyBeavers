"""REFERENCE baseline detector (opt-in, NOT part of the default app path).

Kept under contrib/ as a worked example of the adapter contract that teammates may borrow from or
ignore. Enable only on purpose:  CCT_DETECTOR="contrib.baseline_detector.engine:analyze_releases"


It is NOT the team's detection engine and is never used unless that variable names it. It
contains no knowledge of any specific practice/judging change: it only compares the two folders.

Checks (each derived from the files actually supplied):
  1. File inventory: required files missing from B.
  2. Per-sample profile fingerprints (sha1 of the exact cell text) for every common file.
  3. Membership: ids added/removed per file, called out explicitly when counts are equal.
  4. Swaps: a sample's B profile equals another sample's A profile (exact; reciprocal = swap).
     Plus a correlation-based near-match pass for numeric matrices (lower confidence).
  5. Duplicates: identical non-trivial profiles under different ids in B that were not
     already identical in A.
  6. Missing measurements: features (rows) removed, cells that became empty.
  7. Field-level value changes (clinical labels, survival fields, matrix values in place).
  8. Identifier integrity: malformed TCGA barcodes, sample/patient mismatches, repeated ids.
  9. Subgroup coverage (PAM50 subtype, clinical ER status) of trustworthy primary-tumor profiles.
 10. Mapping of every finding to reference analyses A1/A2, selective reruns, repairs, verdict.
"""
from __future__ import annotations

import hashlib
import re
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from backend import config
from contrib.baseline_detector import impact
from contrib.baseline_detector.tcga_io import MISSING_TOKENS, Profiles, is_primary, patient_of, read_profiles
SAMPLE_RE = re.compile(r"^TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}-\d{2}$")

ENGINE_NAME = "contrib-baseline-reference"
ENGINE_VERSION = "0.3.0"
NEAR_MATCH_MIN_R = 0.98
NEAR_MATCH_MAX_SELF_R = 0.90
NEAR_MATCH_MAX_PROFILES = 300
MAX_EVIDENCE = 60  # cap evidence pointers per finding; the full list goes in `details`

Progress = Callable[[str], None]


@dataclass
class Issue:
    """Internal finding before ids/impact are assigned."""

    kind: str
    file: str | None
    summary: str
    samples: set[str]
    severity_if_affecting: str
    severity_otherwise: str
    confidence: str
    evidence: list[dict]
    limitation: str
    # fields/features whose values changed for these samples; None = whole profile / membership
    fields: set[str] | None = None
    details: dict = field(default_factory=dict)
    repair: dict | None = None  # {"action":..., "targets":[...], "justification":...}
    group: str = ""  # used to merge coverage findings into repairs
    force_affects: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------------- helpers

def _hash_profiles(frame: pd.DataFrame) -> dict[str, str]:
    out = {}
    for col in frame.columns:
        out[col] = hashlib.sha1("\x1f".join(frame[col].tolist()).encode("utf-8")).hexdigest()
    return out


class _LowInfo:
    """Lazy test for profiles with <=1 distinct non-missing value (all zero, all empty...).
    Identical such profiles are expected and are never reported as duplicates or swaps."""

    def __init__(self, frame: pd.DataFrame):
        self.frame, self.cache = frame, {}

    def check(self, sid: str) -> bool:
        if sid not in self.cache:
            col = self.frame[sid]
            self.cache[sid] = col[~col.isin(MISSING_TOKENS)].nunique() <= 1
        return self.cache[sid]


def _ptr(kind: str, id_: str, release: str | None = None, file: str | None = None, note: str | None = None) -> dict:
    p = {"kind": kind, "id": id_}
    if release:
        p["release"] = release
    if file:
        p["file"] = file
    if note:
        p["note"] = note
    return p


def _fmt_list(xs, n=6) -> str:
    xs = sorted(xs)
    return ", ".join(xs[:n]) + (f" and {len(xs) - n} more" if len(xs) > n else "")


def _diff_fields(a: pd.Series, b: pd.Series) -> list[str]:
    a, b = a.align(b, join="inner")
    return list(a.index[(a != b).to_numpy()])


# ----------------------------------------------------------------------------- engine

class Comparison:
    def __init__(self, dir_a: Path, dir_b: Path, name_a: str, name_b: str, progress: Progress | None = None):
        self.dir_a, self.dir_b = Path(dir_a), Path(dir_b)
        self.name_a, self.name_b = name_a, name_b
        self.progress = progress or (lambda msg: None)
        self.issues: list[Issue] = []
        self.notes: list[str] = []
        self.file_stats: dict[str, dict] = {}
        self.flagged: dict[str, set[str]] = defaultdict(set)  # file -> B ids whose profile is untrustworthy
        self.exclude_preview: dict[str, set[str]] = defaultdict(set)  # file -> ids a repair would exclude
        self.labels_a: dict[str, dict[str, str]] = {}
        self.labels_b: dict[str, dict[str, str]] = {}
        self.ids_per_file: dict[str, tuple[set[str], set[str]]] = {}
        self.changed_files: set[str] = set()

    # -- top level ------------------------------------------------------------
    def run(self) -> dict:
        files_a = {f for f in config.KNOWN_FILES if (self.dir_a / f).is_file()}
        files_b = {f for f in config.KNOWN_FILES if (self.dir_b / f).is_file()}
        self._inventory(files_a, files_b)
        self._load_labels(files_a, files_b)
        for f in config.KNOWN_FILES:
            if f in files_a and f in files_b:
                self.progress(f"Comparing {f}")
                self._compare_file(f)
        self.progress("Checking subgroup coverage")
        self._coverage()
        return self._build_report(files_a, files_b)

    # -- inventory ------------------------------------------------------------
    def _inventory(self, files_a: set[str], files_b: set[str]) -> None:
        for f in sorted(files_a - files_b):
            if f in config.OPTIONAL_FILES:
                self.notes.append(f"{f} is present in {self.name_a} but not in {self.name_b}; it was not compared. "
                                  "No reference analysis reads it (A2 uses the PAM50 call stored in clinical.tsv).")
                continue
            self.changed_files.add(f)
            self.issues.append(Issue(
                kind="missing_data", file=f,
                summary=f"Required file {f} is missing from {self.name_b}; every measurement it held is unavailable.",
                samples=set(), severity_if_affecting="high", severity_otherwise="high", confidence="high",
                evidence=[_ptr("file", f, self.name_a, note="present in A"), _ptr("release", self.name_b, note=f"{f} absent")],
                limitation="Cannot tell whether the file was withheld on purpose or lost in packaging.",
                fields=None, force_affects=[a.id for a in impact.ANALYSES.values() if f in a.files],
                repair={"action": "restore_from_previous_release", "targets": [_ptr("file", f, self.name_a)],
                        "justification": f"{f} exists in {self.name_a}; restore it or document why it was removed before using {self.name_b}."}))
        for f in sorted(files_b - files_a):
            self.notes.append(f"{f} is present in {self.name_b} but not in {self.name_a}; nothing to compare it with.")

    def _load_labels(self, files_a, files_b) -> None:
        cols = ("breast_carcinoma_estrogen_receptor_status", "PAM50Call_RNAseq")
        for d, fs, target in ((self.dir_a, files_a, self.labels_a), (self.dir_b, files_b, self.labels_b)):
            if "clinical.tsv" not in fs:
                continue
            df = pd.read_csv(d / "clinical.tsv", sep="\t", dtype=str, keep_default_na=False)
            if "sampleID" not in df.columns:
                continue
            df = df.drop_duplicates("sampleID").set_index("sampleID")
            for c in cols:
                if c in df.columns:
                    target[c] = df[c].to_dict()

    def _label(self, col: str, sid: str) -> str:
        v = self.labels_a.get(col, {}).get(sid) or self.labels_b.get(col, {}).get(sid) or ""
        return v

    # -- per file -------------------------------------------------------------
    def _compare_file(self, f: str) -> None:
        pa = read_profiles(self.dir_a / f, f)
        pb = read_profiles(self.dir_b / f, f)
        A, B = pa.frame, pb.frame
        ids_a, ids_b = set(A.columns), set(B.columns)
        self.ids_per_file[f] = (ids_a, ids_b)
        feats_a, feats_b = list(A.index), set(B.index)
        common_feats = [x for x in feats_a if x in feats_b]
        removed_feats = [x for x in feats_a if x not in feats_b]
        added_feats = sorted(feats_b - set(feats_a))
        Ac, Bc = A.reindex(common_feats), B.reindex(common_feats)
        h_a, h_b = _hash_profiles(Ac), _hash_profiles(Bc)
        low_a, low_b = _LowInfo(Ac), _LowInfo(Bc)

        common = ids_a & ids_b
        added, removed = ids_b - ids_a, ids_a - ids_b
        changed = {x for x in common if h_a[x] != h_b[x]}
        if added or removed or changed or removed_feats or added_feats or pb.duplicate_ids:
            self.changed_files.add(f)
        self.file_stats[f] = {
            "samples_a": len(ids_a), "samples_b": len(ids_b), "added": len(added), "removed": len(removed),
            "profiles_changed": len(changed), "features_a": len(feats_a), "features_b": len(feats_b),
            "features_removed": len(removed_feats), "features_added": len(added_feats),
            "count_equal_membership_differs": len(ids_a) == len(ids_b) and ids_a != ids_b,
        }

        by_hash_a: dict[str, list[str]] = defaultdict(list)
        for sid, h in h_a.items():
            by_hash_a[h].append(sid)
        for h in list(by_hash_a):
            if low_a.check(by_hash_a[h][0]):
                del by_hash_a[h]  # uninformative profile (all empty / all one value)
        explained: set[str] = set()

        # ---- duplicates (new identical profiles in B)
        by_hash_b: dict[str, list[str]] = defaultdict(list)
        for sid, h in h_b.items():
            by_hash_b[h].append(sid)
        for h in list(by_hash_b):
            if len(by_hash_b[h]) > 1 and low_b.check(by_hash_b[h][0]):
                del by_hash_b[h]
        dup_copies: set[str] = set()
        dup_groups: list[dict] = []
        for h, group in by_hash_b.items():
            if len(group) < 2:
                continue
            same_in_a = {s for s in group if h_a.get(s) == h}
            if set(group) <= same_in_a:
                continue  # these ids were already identical in A: pre-existing, not a new problem
            copies = sorted(set(group) - same_in_a)
            origin = sorted(same_in_a) or sorted(by_hash_a.get(h, []))
            dup_copies.update(copies)
            explained.update(copies)
            self.flagged[f].update(copies)
            self.exclude_preview[f].update(copies)
            dup_groups.append({"profile_sha1": h, "copies": copies, "originals": origin, "group": sorted(group)})
        if dup_groups:
            ev, all_ids = [], set()
            for g in dup_groups:
                all_ids.update(g["group"])
                for c in g["copies"]:
                    ev.append(_ptr("sample", c, self.name_b, f,
                                   note=f"profile identical to {', '.join(g['originals']) or 'another id'}"
                                   + (" (id not in A's file: newly added)" if c in added else " (id existed in A with a different profile)")))
                for o in g["originals"]:
                    ev.append(_ptr("sample", o, self.name_b if o in ids_b else self.name_a, f, note="source profile (kept)"))
            copies_all = sorted(c for g in dup_groups for c in g["copies"])
            pairs = "; ".join(f"{', '.join(g['copies'])} = {', '.join(g['originals']) or '?'}" for g in dup_groups[:6])
            self.issues.append(Issue(
                kind="duplicate", file=f,
                summary=(f"{f}: {len(copies_all)} sample id(s) carry a measurement profile identical to another sample's "
                         f"({pairs}{'; …' if len(dup_groups) > 6 else ''}). These profiles were not identical in {self.name_a}."),
                samples=all_ids, severity_if_affecting="high", severity_otherwise="medium", confidence="high",
                evidence=ev[:MAX_EVIDENCE],
                limitation=("Exact identity over every shared feature is strong evidence of copying, but the files cannot say "
                            "which id truly owns the profile; the id that held it in the baseline is assumed to be the original."),
                fields=None, details={"groups": dup_groups},
                repair={"action": "exclude", "targets": [_ptr("sample", c, self.name_b, f) for c in copies_all][:MAX_EVIDENCE],
                        "justification": (f"These ids in {f} hold a copy of another sample's profile, so the measurements are "
                                          "not their own. Exclude them from analyses that use this file until the source is confirmed.")},
                group=f"cov:{f}"))

        # ---- swaps / relabels by exact profile match
        swap_pairs: set[tuple[str, str]] = set()
        one_way: list[tuple[str, str]] = []
        for x in sorted((changed | added) - dup_copies):
            if low_b.check(x):
                continue
            cands = [y for y in by_hash_a.get(h_b[x], []) if y != x]
            if not cands:
                continue
            y = cands[0]
            if x in common and y in common and h_b.get(y) == h_a.get(x):
                swap_pairs.add(tuple(sorted((x, y))))
            elif y in ids_b and h_b.get(y) == h_a[y]:
                continue  # y still has its own profile -> x is a duplicate, handled above
            else:
                one_way.append((x, y))
        for a_, b_ in sorted(swap_pairs):
            explained.update((a_, b_))
            self.flagged[f].update((a_, b_))
            self.exclude_preview[f].update((a_, b_))
            fields_changed = set(_diff_fields(Ac[a_], Bc[a_])) | set(_diff_fields(Ac[b_], Bc[b_]))
            er = {s: self._label("breast_carcinoma_estrogen_receptor_status", s) or "unknown" for s in (a_, b_)}
            pam = {s: self._label("PAM50Call_RNAseq", s) or "unknown" for s in (a_, b_)}
            self.issues.append(Issue(
                kind="sample_swap", file=f,
                summary=(f"{f}: the profiles of {a_} and {b_} are exchanged. {self.name_b}'s {a_} equals {self.name_a}'s {b_} "
                         f"and vice versa (clinical ER: {er[a_]} vs {er[b_]}; PAM50: {pam[a_]} vs {pam[b_]})."),
                samples={a_, b_}, severity_if_affecting="high", severity_otherwise="medium", confidence="high",
                evidence=[_ptr("sample", a_, self.name_b, f, note=f"B profile == A profile of {b_}; clinical ER {er[a_]}"),
                          _ptr("sample", b_, self.name_b, f, note=f"B profile == A profile of {a_}; clinical ER {er[b_]}"),
                          _ptr("sample", a_, self.name_a, f, note="original profile"),
                          _ptr("sample", b_, self.name_a, f, note="original profile")],
                limitation=("Exact profile identity across releases shows the labels moved, not which release is correct; "
                            "the baseline is assumed correct."),
                fields=fields_changed, details={"pair": [a_, b_], "features_differing": len(fields_changed)},
                repair={"action": "restore_from_previous_release",
                        "targets": [_ptr("sample", a_, self.name_b, f), _ptr("sample", b_, self.name_b, f)],
                        "justification": (f"Restore the {f} profiles of {a_} and {b_} from {self.name_a}, where each matched "
                                          "its own id; until then exclude both from analyses using this file.")},
                group=f"cov:{f}"))
        for x, y in one_way:
            explained.add(x)
            self.flagged[f].add(x)
            self.exclude_preview[f].add(x)
            self.issues.append(Issue(
                kind="sample_swap", file=f,
                summary=(f"{f}: {x} in {self.name_b} carries the exact profile that belonged to {y} in {self.name_a} "
                         f"({'which is gone from' if y not in ids_b else 'which changed in'} {self.name_b}): the profile was relabelled."),
                samples={x, y}, severity_if_affecting="high", severity_otherwise="medium", confidence="medium",
                evidence=[_ptr("sample", x, self.name_b, f, note=f"B profile == A profile of {y}"),
                          _ptr("sample", y, self.name_a, f, note="original owner of the profile")],
                limitation="A one-way move can be a legitimate barcode correction; the files alone cannot tell.",
                fields=None, details={"new_id": x, "previous_id": y},
                repair={"action": "flag_for_review", "targets": [_ptr("sample", x, self.name_b, f), _ptr("sample", y, self.name_a, f)],
                        "justification": "Confirm with the data provider which barcode this profile belongs to before using it."},
                group=f"cov:{f}"))

        # ---- removed features (rows)
        if removed_feats:
            used = {a.id for a in impact.ANALYSES.values() if f in a.files and (
                (pa.layout == "table" and set(removed_feats) & set(a.clinical_columns)) or
                (pa.layout == "matrix" and set(removed_feats) & set(a.matrix_features.get(f, ()))))}
            self.issues.append(Issue(
                kind="missing_data", file=f,
                summary=f"{f}: {len(removed_feats)} {'column' if pa.layout == 'table' else 'feature row'}(s) removed in {self.name_b} ({_fmt_list(removed_feats)}).",
                samples=set(ids_b), severity_if_affecting="high", severity_otherwise="medium", confidence="high",
                evidence=[_ptr("file", f, self.name_b, note=f"missing: {_fmt_list(removed_feats, 20)}")],
                limitation="Removed features cannot be recovered from release B.",
                fields=set(removed_feats), force_affects=sorted(used), details={"removed_features": removed_feats},
                repair={"action": "restore_from_previous_release", "targets": [_ptr("file", f, self.name_a)],
                        "justification": "Restore the removed features from the previous release or document the removal."}))
        if added_feats:
            self.notes.append(f"{f}: {len(added_feats)} new feature(s) in {self.name_b} ({_fmt_list(added_feats)}); new features are not compared.")

        # ---- remaining changed profiles: missing cells, value edits, near-match swaps
        rest = sorted(changed - explained)
        lost_cells, value_edits = {}, {}
        for x in rest:
            diff = _diff_fields(Ac[x], Bc[x])
            if not diff:
                continue
            miss_a_x = Ac.loc[diff, x].isin(MISSING_TOKENS)
            miss_b_x = Bc.loc[diff, x].isin(MISSING_TOKENS)
            became_missing = [d for d in diff if miss_b_x[d] and not miss_a_x[d]]
            other = [d for d in diff if d not in set(became_missing)]
            if became_missing:
                lost_cells[x] = became_missing
            if other:
                value_edits[x] = other

        if pa.layout == "matrix" and value_edits and len(value_edits) <= NEAR_MATCH_MAX_PROFILES:
            matched = self._near_match(f, Ac, Bc, sorted(value_edits), ids_a)
            for x in matched:
                value_edits.pop(x, None)

        if lost_cells:
            samples = set(lost_cells)
            fields_ = set().union(*lost_cells.values())
            self.flagged[f].update(s for s, v in lost_cells.items() if len(v) >= max(1, len(common_feats) // 2))
            self.issues.append(Issue(
                kind="missing_data", file=f,
                summary=(f"{f}: {len(samples)} sample(s) lost {sum(len(v) for v in lost_cells.values())} measurement(s) "
                         f"that were present in {self.name_a} (e.g. {_fmt_list(samples, 4)})."),
                samples=samples, severity_if_affecting="high", severity_otherwise="medium", confidence="high",
                evidence=[_ptr("sample", s, self.name_b, f, note=f"now empty: {_fmt_list(v, 5)}") for s, v in sorted(lost_cells.items())][:MAX_EVIDENCE],
                limitation="The files cannot show whether values were withdrawn deliberately (e.g. QC failure) or lost.",
                fields=fields_, details={"cells_lost": {s: v[:50] for s, v in lost_cells.items()}},
                repair={"action": "restore_from_previous_release",
                        "targets": [_ptr("sample", s, self.name_a, f) for s in sorted(samples)][:MAX_EVIDENCE],
                        "justification": "Values exist in the previous release; restore them or record why they were withdrawn."},
                group=f"cov:{f}"))

        if value_edits:
            self._value_edit_issues(f, pa.layout, Ac, Bc, value_edits)

        # ---- membership
        if added or removed:
            eq = len(ids_a) == len(ids_b)
            plain_added = sorted(added - dup_copies - explained)
            self.issues.append(Issue(
                kind="membership_change", file=f,
                summary=(f"{f}: membership changed{' although the sample count is identical' if eq else ''} "
                         f"({len(ids_a)} → {len(ids_b)}): {len(removed)} removed ({_fmt_list(removed, 5)}), "
                         f"{len(added)} added ({_fmt_list(added, 5)})."),
                samples=added | removed, severity_if_affecting="high", severity_otherwise="medium", confidence="high",
                evidence=([_ptr("sample", s, self.name_a, f, note=f"in {self.name_a}, absent from {self.name_b}") for s in sorted(removed)] +
                          [_ptr("sample", s, self.name_b, f, note=f"new in {self.name_b}") for s in sorted(added)])[:MAX_EVIDENCE],
                limitation=("Equal counts never prove equal membership; this is a direct id comparison. Whether a "
                            "removal was intended (e.g. withdrawn consent, QC) is not recorded in the files."),
                fields=None, details={"removed": sorted(removed), "added": sorted(added), "count_equal": eq,
                                       "added_without_profile_match": plain_added},
                repair={"action": "restore_from_previous_release" if removed else "flag_for_review",
                        "targets": ([_ptr("sample", s, self.name_a, f) for s in sorted(removed)] +
                                    [_ptr("sample", s, self.name_b, f) for s in plain_added])[:MAX_EVIDENCE],
                        "justification": (f"Samples removed from {f} should be restored from {self.name_a} or their removal documented; "
                                          "newly added samples need provenance before they enter an analysis.")},
                group=f"cov:{f}"))

        # ---- identifier integrity
        self._id_integrity(f, pb, ids_a, ids_b, B)

    def _near_match(self, f, Ac, Bc, xs, ids_a) -> set[str]:
        """Correlation search for profiles that moved between ids with small numeric edits."""
        try:
            Na = Ac.apply(pd.to_numeric, errors="coerce")
            Nb = Bc[xs].apply(pd.to_numeric, errors="coerce")
        except Exception:  # non-numeric file
            return set()
        keep = Na.notna().mean(axis=1) > 0.5
        Na, Nb = Na[keep], Nb[keep]
        if Na.shape[0] < 5:
            return set()
        mu = Na.mean(axis=1)
        Na, Nb = Na.sub(mu, axis=0).fillna(0.0), Nb.sub(mu, axis=0).fillna(0.0)

        def z(m):
            v = m.to_numpy(dtype=float)
            v = v - v.mean(axis=0)
            sd = np.sqrt((v ** 2).sum(axis=0))
            sd[sd == 0] = np.nan
            return v / sd
        za, zb = z(Na), z(Nb)
        r = np.nan_to_num(zb.T @ za)
        cols_a = list(Na.columns)
        pos = {c: i for i, c in enumerate(cols_a)}
        found: dict[str, tuple[str, float, float]] = {}
        for i, x in enumerate(xs):
            j = int(np.argmax(r[i]))
            best, rb = cols_a[j], float(r[i, j])
            self_r = float(r[i, pos[x]]) if x in pos else 0.0
            if best != x and rb >= NEAR_MATCH_MIN_R and self_r < NEAR_MATCH_MAX_SELF_R:
                found[x] = (best, rb, self_r)
        done = set()
        for x, (y, rb, sr) in sorted(found.items()):
            if x in done:
                continue
            reciprocal = y in found and found[y][0] == x
            pair = sorted({x, y}) if reciprocal else [x]
            done.update(pair)
            for s in pair:
                self.flagged[f].add(s)
                self.exclude_preview[f].add(s)
            self.issues.append(Issue(
                kind="sample_swap", file=f,
                summary=(f"{f}: {x}'s profile in {self.name_b} correlates r={rb:.3f} with {y}'s profile in {self.name_a} but only "
                         f"r={sr:.3f} with its own previous profile{' (reciprocal: likely swap)' if reciprocal else ''}."),
                samples={x, y}, severity_if_affecting="high", severity_otherwise="medium",
                confidence="medium" if reciprocal else "low",
                evidence=[_ptr("sample", x, self.name_b, f, note=f"r={rb:.3f} vs {y} in A; r={sr:.3f} vs itself in A"),
                          _ptr("sample", y, self.name_a, f, note="best-matching previous profile")],
                limitation="Correlation-based: similar but not identical profiles; could be re-normalisation plus coincidence.",
                fields=None, details={"sample": x, "best_match": y, "r_best": rb, "r_self": sr, "reciprocal": reciprocal},
                repair={"action": "flag_for_review", "targets": [_ptr("sample", s, self.name_b, f) for s in pair],
                        "justification": "Profiles appear to have moved between ids; confirm identity before use."},
                group=f"cov:{f}"))
        return done

    def _value_edit_issues(self, f, layout, Ac, Bc, edits: dict[str, list[str]]) -> None:
        if layout == "table":
            by_field: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
            for s, fields_ in edits.items():
                for fld in fields_:
                    by_field[fld][s] = (Ac.at[fld, s], Bc.at[fld, s])
            for fld, changes in sorted(by_field.items()):
                transitions = defaultdict(int)
                for b, a in changes.values():
                    transitions[f"'{b}' → '{a}'"] += 1
                top = ", ".join(f"{k} ×{v}" for k, v in sorted(transitions.items(), key=lambda kv: -kv[1])[:4])
                self.issues.append(Issue(
                    kind="label_conflict" if f == "clinical.tsv" else "other", file=f,
                    summary=f"{f}: field '{fld}' changed for {len(changes)} sample(s) ({top}).",
                    samples=set(changes), severity_if_affecting="high", severity_otherwise="low", confidence="high",
                    evidence=[_ptr("sample", s, self.name_b, f, note=f"{fld}: '{b}' in {self.name_a} → '{a}' in {self.name_b}")
                              for s, (b, a) in sorted(changes.items())][:MAX_EVIDENCE],
                    limitation="A changed label may be a legitimate correction; only the data provider can confirm which value is right.",
                    fields={fld}, details={"field": fld, "changes": {s: {"before": b, "after": a} for s, (b, a) in changes.items()}},
                    repair={"action": "flag_for_review", "targets": [_ptr("sample", s, self.name_b, f) for s in sorted(changes)][:MAX_EVIDENCE],
                            "justification": f"Confirm the new '{fld}' values against source records; if unconfirmed, keep the {self.name_a} values."}))
        else:
            samples = set(edits)
            fields_ = set().union(*edits.values())
            for s, v in edits.items():
                if len(v) >= max(1, len(Ac.index) // 2):
                    self.flagged[f].add(s)
            self.issues.append(Issue(
                kind="other", file=f,
                summary=(f"{f}: measurement values changed in place for {len(samples)} sample(s) "
                         f"({sum(len(v) for v in edits.values())} cells; e.g. {_fmt_list(samples, 4)})."),
                samples=samples, severity_if_affecting="high", severity_otherwise="low", confidence="medium",
                evidence=[_ptr("sample", s, self.name_b, f, note=f"{len(v)} value(s) differ: {_fmt_list(v, 5)}")
                          for s, v in sorted(edits.items())][:MAX_EVIDENCE],
                limitation="In-place edits may be reprocessing (new normalisation) rather than error; the files carry no processing log.",
                fields=fields_, details={"cells_changed": {s: v[:50] for s, v in edits.items()}},
                repair={"action": "flag_for_review", "targets": [_ptr("sample", s, self.name_b, f) for s in sorted(samples)][:MAX_EVIDENCE],
                        "justification": "Ask the provider whether the values were reprocessed; otherwise restore the previous values."},
                group=f"cov:{f}"))

    def _id_integrity(self, f: str, pb: Profiles, ids_a, ids_b, B: pd.DataFrame) -> None:
        bad = sorted(s for s in ids_b - ids_a if not SAMPLE_RE.match(s))
        if bad:
            self.issues.append(Issue(
                kind="unlinked_record", file=f,
                summary=f"{f}: {len(bad)} new id(s) are not valid 15-character TCGA sample barcodes ({_fmt_list(bad)}).",
                samples=set(bad), severity_if_affecting="medium", severity_otherwise="medium", confidence="high",
                evidence=[_ptr("sample", s, self.name_b, f, note="malformed barcode") for s in bad][:MAX_EVIDENCE],
                limitation="Malformed ids cannot be linked to patients or other layers.", fields=None,
                repair={"action": "exclude", "targets": [_ptr("sample", s, self.name_b, f) for s in bad][:MAX_EVIDENCE],
                        "justification": "Records that cannot be linked to a patient should not enter joined analyses."}))
        if pb.duplicate_ids:
            self.issues.append(Issue(
                kind="duplicate", file=f,
                summary=f"{f}: id(s) appear more than once in {self.name_b} ({_fmt_list(pb.duplicate_ids)}); only the first copy was compared.",
                samples=set(pb.duplicate_ids), severity_if_affecting="high", severity_otherwise="medium", confidence="high",
                evidence=[_ptr("sample", s, self.name_b, f, note="repeated id") for s in pb.duplicate_ids][:MAX_EVIDENCE],
                limitation="Which repeated record is authoritative is unknown.", fields=None,
                repair={"action": "flag_for_review", "targets": [_ptr("sample", s, self.name_b, f) for s in pb.duplicate_ids][:MAX_EVIDENCE],
                        "justification": "Keep one record per id after confirming which is correct."}))
        if pb.layout == "table" and "_PATIENT" in B.index:
            pt = B.loc["_PATIENT"]
            mism = sorted(s for s in B.columns if SAMPLE_RE.match(s) and pt[s] not in MISSING_TOKENS and pt[s] != patient_of(s))
            prev = set()
            if f in self.ids_per_file:
                pa = read_profiles(self.dir_a / f, f).frame
                if "_PATIENT" in pa.index:
                    prev = {s for s in pa.columns if SAMPLE_RE.match(s) and pa.at["_PATIENT", s] != patient_of(s)}
            new_mism = [s for s in mism if s not in prev]
            if new_mism:
                self.issues.append(Issue(
                    kind="label_conflict", file=f,
                    summary=f"{f}: {len(new_mism)} sample(s) have a _PATIENT value that does not match their barcode ({_fmt_list(new_mism)}).",
                    samples=set(new_mism), severity_if_affecting="high", severity_otherwise="medium", confidence="high",
                    evidence=[_ptr("sample", s, self.name_b, f, note=f"_PATIENT={pt[s]}") for s in new_mism][:MAX_EVIDENCE],
                    limitation="Barcode convention: the first 12 characters of a sample id are the patient id.", fields={"_PATIENT"},
                    repair={"action": "flag_for_review", "targets": [_ptr("sample", s, self.name_b, f) for s in new_mism][:MAX_EVIDENCE],
                            "justification": "Patient linkage is inconsistent; resolve before joining layers."}))

    # -- subgroup coverage ----------------------------------------------------
    def _coverage(self) -> None:
        groupings = {"PAM50 subtype": "PAM50Call_RNAseq", "clinical ER status": "breast_carcinoma_estrogen_receptor_status"}
        self.coverage_tables: dict[str, list[dict]] = {}
        for f, (ids_a, ids_b) in self.ids_per_file.items():
            if f == "clinical.tsv":
                continue
            trusted_b = ids_b - self.flagged.get(f, set())
            rows, changed_groups, affected = [], [], set()
            for gname, col in groupings.items():
                if not self.labels_a.get(col) and not self.labels_b.get(col):
                    continue
                labels = defaultdict(lambda: [0, 0])
                for s in ids_a:
                    if is_primary(s):
                        labels[self._label(col, s) or "(no label)"][0] += 1
                for s in trusted_b:
                    if is_primary(s):
                        labels[self._label(col, s) or "(no label)"][1] += 1
                for lab, (na, nb) in sorted(labels.items()):
                    rows.append({"grouping": gname, "group": lab, "n_a": na, "n_b_trusted": nb, "delta": nb - na})
                    if na != nb and lab != "(no label)":
                        changed_groups.append(f"{gname} {lab}: {na} → {nb} ({nb - na:+d})")
            self.coverage_tables[f] = rows
            if not changed_groups:
                continue
            lost = {s for s in ids_a if is_primary(s)} - trusted_b
            gained = {s for s in trusted_b if is_primary(s)} - ids_a
            affected = lost | gained
            self.issues.append(Issue(
                kind="missing_data", file=f,
                summary=(f"{f}: primary-tumor coverage by subgroup changed once removed or untrustworthy profiles are set aside — "
                         + "; ".join(changed_groups[:8]) + ("; …" if len(changed_groups) > 8 else "") + "."),
                samples=affected, severity_if_affecting="medium", severity_otherwise="medium", confidence="high",
                evidence=[_ptr("file", f, self.name_b, note="; ".join(changed_groups[:20]))] +
                         [_ptr("sample", s, self.name_a, f, note="trustworthy in A, not in B") for s in sorted(lost)][:MAX_EVIDENCE],
                limitation=("Subgroup labels come from clinical.tsv (A, falling back to B). Counts treat swapped, duplicated "
                            "or emptied profiles as not trustworthy; they are still physically present in the file."),
                fields=None, details={"table": rows}, group=f"cov:{f}"))

    # -- impact, reruns, repairs, verdict ------------------------------------
    def _eligible(self, spec: impact.AnalysisSpec, s: str) -> bool:
        if not is_primary(s):
            return False
        if spec.id == "A1":
            col = "breast_carcinoma_estrogen_receptor_status"
            return any(lbl.get(col, {}).get(s) in ("Positive", "Negative") for lbl in (self.labels_a, self.labels_b))
        if spec.id == "A2":
            col = "PAM50Call_RNAseq"
            return any(lbl.get(col, {}).get(s) for lbl in (self.labels_a, self.labels_b))
        return True

    def _affects(self, iss: Issue) -> tuple[list[str], list[str], dict[str, str]]:
        aff, not_aff, why = [], [], {}
        for spec in impact.ANALYSES.values():
            if spec.id in iss.force_affects:
                aff.append(spec.id)
                why[spec.id] = f"{spec.id} reads {iss.file}"
                continue
            if iss.file not in spec.files:
                not_aff.append(spec.id)
                why[spec.id] = f"{spec.id} does not read {iss.file}"
                continue
            relevant = {s for s in iss.samples if self._eligible(spec, s)}
            if not relevant:
                not_aff.append(spec.id)
                why[spec.id] = f"none of the samples involved meet {spec.id}'s inclusion criteria"
                continue
            if iss.fields is not None:
                used = set(spec.clinical_columns) if iss.file == "clinical.tsv" else set(spec.matrix_features.get(iss.file) or ())
                if iss.file != "clinical.tsv" and spec.matrix_features.get(iss.file) is None:
                    used = set(iss.fields)
                if not (iss.fields & used):
                    not_aff.append(spec.id)
                    why[spec.id] = f"{spec.id} does not use the changed field(s) ({_fmt_list(iss.fields, 3)})"
                    continue
            aff.append(spec.id)
            why[spec.id] = f"{len(relevant)} involved sample(s) are {spec.id} inputs in {iss.file}"
        return aff, not_aff, why

    def _build_report(self, files_a: set[str], files_b: set[str]) -> dict:
        sev_rank = {"high": 0, "medium": 1, "low": 2, "none": 3}
        mapped = []
        for iss in self.issues:
            aff, not_aff, why = self._affects(iss)
            sev = iss.severity_if_affecting if aff else iss.severity_otherwise
            mapped.append((iss, aff, not_aff, why, sev))
        kind_rank = {"missing_data": 3, "sample_swap": 0, "duplicate": 1, "membership_change": 2, "label_conflict": 4}
        mapped.sort(key=lambda m: (sev_rank[m[4]], kind_rank.get(m[0].kind, 9), m[0].file or "", m[0].summary))

        findings, repairs = [], []
        group_to_findings: dict[str, list[str]] = defaultdict(list)
        finding_ids: dict[int, str] = {}
        for i, (iss, aff, not_aff, why, sev) in enumerate(mapped, 1):
            fid = f"F{i:02d}"
            finding_ids[id(iss)] = fid
            if iss.group:
                group_to_findings[iss.group].append(fid)
            findings.append({
                "id": fid, "kind": iss.kind, "summary": iss.summary, "severity": sev, "confidence": iss.confidence,
                "evidence": iss.evidence or [_ptr("file", iss.file or "", self.name_b)],
                "affects_analyses": aff, "not_affected_analyses": not_aff,
                "limitation": iss.limitation, "needs_human_review": sev in ("high", "medium"),
                "file": iss.file, "impact_reasons": why, "details": iss.details,
            })
        r = 0
        for (iss, aff, not_aff, why, sev) in mapped:
            if not iss.repair:
                continue
            r += 1
            fid = finding_ids[id(iss)]
            addresses = [fid]
            # coverage findings for the same file are resolved by the same repairs
            for other in group_to_findings.get(iss.group, []):
                o = next(f for f in findings if f["id"] == other)
                if other != fid and o["kind"] == "missing_data" and "subgroup" in o["summary"] and other not in addresses:
                    addresses.append(other)
            repairs.append({"id": f"R{r:02d}", "action": iss.repair["action"],
                            "targets": iss.repair["targets"] or [_ptr("file", iss.file or "", self.name_b)],
                            "justification": iss.repair["justification"] + " Requires researcher approval; nothing is changed automatically.",
                            "addresses": addresses})

        # analyses: before always from A; rerun only where a finding maps (or an unexplained input change)
        self.progress("Rerunning affected analyses")
        analyses = []
        for spec in impact.ANALYSES.values():
            triggered = [f["id"] for f in findings if spec.id in f["affects_analyses"]]
            entry: dict = {"id": spec.id, "title": spec.title, "inputs": list(spec.files), "triggered_by": triggered}
            missing_in = [f for f in spec.files if f not in files_a or f not in files_b]
            before_full = None
            if all(f in files_a for f in spec.files):
                try:
                    before_full = impact.run_analysis(spec.id, self.dir_a)
                    entry["before"] = impact.summarize(before_full)
                except Exception as e:  # report honestly, never fabricate
                    entry["before_error"] = f"{type(e).__name__}: {e}"
            unexplained = [f for f in spec.files if f in self.changed_files] if not triggered else []
            if not triggered and not unexplained:
                entry["status"] = "not_rerun"
                changed_inputs = [f for f in spec.files if f in self.changed_files]
                entry["reason"] = (
                    f"No finding touches {spec.id}'s inputs: " + (
                        f"{', '.join(spec.files)} content is identical between releases." if not changed_inputs else
                        "the changes in " + ", ".join(changed_inputs) + " involve fields or samples it does not use."))
                analyses.append(entry)
                continue
            if missing_in:
                entry["status"] = "not_rerun"
                entry["reason"] = f"Cannot rerun: {', '.join(missing_in)} missing from a release."
                analyses.append(entry)
                continue
            try:
                after_full = impact.run_analysis(spec.id, self.dir_b)
                entry["after"] = impact.summarize(after_full)
                cmp = impact.compare_results(before_full or {}, after_full)
                entry["comparison"] = cmp
                entry["status"] = "changed" if (cmp["result_changed"] or cmp["membership_changed"]) else "unchanged"
                if triggered and entry["status"] == "unchanged":
                    entry["reason"] = ("Rerun because findings touch its inputs; the summary numbers did not move, but the "
                                       "affected records are still flagged for review.")
                elif triggered:
                    entry["reason"] = f"Rerun because finding(s) {', '.join(triggered)} change records it uses."
                else:
                    entry["reason"] = ("Rerun as a precaution: an input file changed but no finding explains the change "
                                       "(possible detector blind spot).")
                excl = {f: ids for f, ids in self.exclude_preview.items() if f in spec.files and ids}
                if excl:
                    prev = impact.run_analysis(spec.id, self.dir_b, exclude=excl)
                    entry["after_excluding_flagged"] = {
                        **impact.summarize(prev),
                        "excluded": {f: sorted(v) for f, v in excl.items()},
                        "note": "Preview of the proposed exclusions (computed in memory; release files untouched).",
                    }
            except Exception as e:
                entry["status"] = "not_rerun"
                entry["reason"] = f"Rerun failed: {type(e).__name__}: {e}"
            analyses.append(entry)

        verdict = self._verdict(findings, analyses)
        return {
            "findings": findings, "repairs": repairs, "analyses": analyses, "verdict": verdict,
            "notes": self.notes, "file_stats": self.file_stats,
            "coverage": getattr(self, "coverage_tables", {}),
        }

    @staticmethod
    def _verdict(findings, analyses) -> str:
        if any(a.get("status") == "not_rerun" and a.get("reason", "").startswith(("Cannot", "Rerun failed")) for a in analyses):
            return "Insufficient Evidence"
        if any(f["severity"] == "high" and f["affects_analyses"] for f in findings):
            return "Blocked"
        if any(f["needs_human_review"] for f in findings):
            return "Conditional"
        if findings:
            return "Conditional"
        return "Ready"


def analyze_releases(release_a: str, release_b: str, output_path: str, *,
                     release_names: tuple[str, str] | None = None, progress: Progress | None = None) -> dict:
    """Adapter-compatible entry point. Writes findings.json-compatible content to output_path.

    Returns a dict with keys ``findings``, ``repairs``, ``analyses``, ``verdict`` plus
    builtin-only extras (``notes``, ``file_stats``, ``coverage``) that the adapter moves to
    the run summary. The adapter adds ``format_version``, ``producer``, ``data`` and ``question``.
    """
    a, b = Path(release_a), Path(release_b)
    names = release_names or (a.name, b.name)
    result = Comparison(a, b, names[0], names[1], progress).run()
    Path(output_path).write_text(json.dumps(result, indent=2, default=str))
    return result
