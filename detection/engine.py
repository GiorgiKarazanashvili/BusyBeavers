"""Cohort Firewall detection engine for the Control Tower API.

Contract (see contrib/engine_template.py):
    analyze_releases(release_a, release_b, output_path, *, release_names=None, progress=None) -> dict

This module only translates: cfw (load / fingerprint / diff / impact) does the detection;
here its raw findings are merged into event-level v0.2 findings, mapped to analyses,
the affected analyses are rerun with the organizers' reference_analyses.py, and repairs
and a verdict are proposed. Nothing in here knows about specific sample ids.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cfw.compare import compare             # noqa: E402
from cfw.impact import ANALYSES             # noqa: E402

ENGINE_NAME = "cohort-firewall-cfw"
MAX_EVIDENCE = 500
REF_PATH = ROOT / "data" / "tcga-brca" / "reference_analyses.py"
# stems (cfw names files by stem) each analysis reads; used for file-level findings
ANALYSIS_FILES = {"A1": {"clinical", "protein_rppa"}, "A2": {"clinical"}}


def _ref():
    spec = importlib.util.spec_from_file_location("cct_reference_analyses", REF_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _filenames(release_dir: Path) -> dict[str, str]:
    """stem -> real file name, e.g. protein_rppa -> protein_rppa.tsv.gz"""
    return {p.name.split(".")[0]: p.name for p in release_dir.glob("*.tsv*")}


def _ptr(id_, release, file, note=None, kind="sample"):
    p = {"kind": kind, "id": id_, "release": release, "file": file}
    if note:
        p["note"] = note
    return p


def _fmt(ids, n=5):
    ids = list(ids)
    return ", ".join(ids[:n]) + (f" (+{len(ids) - n} more)" if len(ids) > n else "")


def _group(raw):
    """Group cfw's raw findings by (file, type)."""
    g: dict[tuple, list[dict]] = {}
    for f in raw:
        g.setdefault((f["file"], f["type"]), []).append(f)
    return g


def _events(raw, fn_a, fn_b, name_a, name_b):
    """Raw cfw findings -> event-level findings (no ids / impact yet)."""
    groups = _group(raw)
    events = []

    def fname(stem, which="b"):
        return (fn_b if which == "b" else fn_a).get(stem) or fn_a.get(stem) or fn_b.get(stem) or stem

    for (stem, typ), items in sorted(groups.items()):
        ids = sorted({i for it in items for i in it["sample_ids"]})
        file_b, file_a = fname(stem, "b"), fname(stem, "a")

        if typ == "swap":
            pairs = [it["sample_ids"] for it in items]
            ev = []
            for x, y in pairs:
                ev.append(_ptr(x, name_b, file_b, f"{file_b}: profile equals {y}'s profile in release A (and vice versa)"))
                ev.append(_ptr(y, name_b, file_b, f"{file_b}: profile equals {x}'s profile in release A (and vice versa)"))
            events.append(dict(
                kind="sample_swap", file=stem, ids=ids, severity_hi="high", severity_lo="medium", confidence="high",
                summary=f"{file_b}: {len(pairs)} pair(s) of samples exchanged their measurements "
                        f"({'; '.join(' <-> '.join(p) for p in pairs[:3])}{' ...' if len(pairs) > 3 else ''}).",
                evidence=ev,
                limitation="Exact profile identity shows the labels moved, not which release is correct.",
                repair=dict(action="restore_from_previous_release", ids=ids, file=file_b,
                            why=f"Restore the release A profiles for these samples in {file_b}, or exclude them until the provider confirms the correct assignment.")))

        elif typ == "duplicate_profile":
            added = {i for it in groups.get((stem, "samples_added"), []) for i in it["sample_ids"]}
            ev, new_ids = [], set()
            for it in items:
                members = it["sample_ids"]
                new = [m for m in members if m in added]
                orig = [m for m in members if m not in added]
                new_ids |= set(new)
                for m in members:
                    others = [o for o in members if o != m]
                    role = "new id in B" if m in added else "id present in A"
                    ev.append(_ptr(m, name_b, file_b, f"{file_b}: {role}; identical profile to {_fmt(others, 3)}"))
            events.append(dict(
                kind="duplicate", file=stem, ids=ids, severity_hi="high", severity_lo="medium", confidence="high",
                summary=f"{file_b}: {len(items)} identical-profile group(s) in release B that were not identical in release A"
                        f"{f'; {len(new_ids)} of the ids are new in B' if new_ids else ''}.",
                evidence=ev,
                limitation="Identical measurements under different ids strongly suggest copying, but the files cannot say which id is genuine.",
                repair=dict(action="exclude" if new_ids else "flag_for_review", ids=sorted(new_ids) or ids, file=file_b,
                            why=f"Exclude the duplicated ids from {file_b} analyses until their origin is confirmed." if new_ids
                                else f"Confirm with the provider which of the identical profiles in {file_b} is genuine.")))

        elif typ in ("samples_added", "samples_removed"):
            dup_ids = {i for it in groups.get((stem, "duplicate_profile"), []) for i in it["sample_ids"]}
            if typ == "samples_added":
                other = {i for it in groups.get((stem, "samples_removed"), []) for i in it["sample_ids"]}
                note = f"{file_b}: id absent from release A"
                rel, fl = name_b, file_b
            else:
                other = {i for it in groups.get((stem, "samples_added"), []) for i in it["sample_ids"]}
                note = f"{file_a}: id present in release A, absent from release B"
                rel, fl = name_a, file_a
            ev = []
            for i in ids:
                n = note + ("; its profile is identical to another sample's (see duplicate finding)" if i in dup_ids else "")
                ev.append(_ptr(i, rel, fl, n))
            word = "added" if typ == "samples_added" else "removed"
            same = f" Counts can stay equal while membership changes ({len(other)} sample(s) went the other way)." if other else ""
            events.append(dict(
                kind="membership_change", file=stem, ids=ids, severity_hi="high", severity_lo="medium", confidence="high",
                summary=f"{(file_b if typ == 'samples_added' else file_a)}: {len(ids)} sample id(s) {word} between releases.{same}",
                evidence=ev,
                limitation="Direct id comparison; whether the change is deliberate (QC, re-processing) is not visible in the files.",
                repair=dict(action="restore_from_previous_release" if typ == "samples_removed" else "flag_for_review",
                            ids=ids, file=file_a if typ == "samples_removed" else file_b,
                            why=("Restore these samples from release A if their removal was unintended." if typ == "samples_removed"
                                 else "Confirm that these new ids belong in the release and have genuine measurements."))))

        elif typ == "profile_modified":
            cols = sorted({c for it in items for c in it.get("columns_changed", [])})
            ev = [_ptr(it["sample_ids"][0], name_b, file_b,
                       f"{file_b}: values differ from release A" + (f" in {_fmt(it['columns_changed'], 4)}" if it.get("columns_changed") else ""))
                  for it in items]
            events.append(dict(
                kind="label_conflict" if stem in ("clinical", "survival") else "other", file=stem, ids=ids,
                severity_hi="high", severity_lo="low", confidence="high",
                summary=f"{file_b}: values changed in place for {len(ids)} sample(s)" + (f" (fields: {_fmt(cols, 5)})." if cols else "."),
                evidence=ev,
                limitation="A changed value may be a legitimate correction; only the data provider can confirm.",
                repair=dict(action="flag_for_review", ids=ids, file=file_b,
                            why="Confirm the new values against source records; if unconfirmed, keep the release A values.")))

        elif typ == "missingness_increased":
            events.append(dict(
                kind="missing_data", file=stem, ids=ids, severity_hi="high", severity_lo="medium", confidence="medium",
                summary=f"{file_b}: {len(ids)} sample(s) have noticeably more missing measurements in B than in A.",
                evidence=[_ptr(i, name_b, file_b, "share of missing values rose by more than 5 percentage points") for i in ids],
                limitation="Cannot tell whether values were withdrawn deliberately or lost.",
                repair=dict(action="flag_for_review", ids=ids, file=file_b,
                            why="Check whether the missing values were withdrawn on purpose; consider restoring them from release A.")))

        elif typ == "duplicate_id":
            events.append(dict(
                kind="duplicate", file=stem, ids=ids, severity_hi="high", severity_lo="medium", confidence="high",
                summary=f"{file_b}: {len(ids)} sample id(s) appear more than once.",
                evidence=[_ptr(i, name_b, file_b, "id repeated within the file") for i in ids],
                limitation="Which repeated record is authoritative is unknown.",
                repair=dict(action="flag_for_review", ids=ids, file=file_b, why="Decide which repeated record to keep.")))

        elif typ in ("file_removed", "file_added"):
            word = "missing from release B" if typ == "file_removed" else "new in release B"
            f = file_a if typ == "file_removed" else file_b
            events.append(dict(
                kind="membership_change", file=stem, ids=[], severity_hi="high", severity_lo="medium", confidence="high",
                summary=f"{f} is {word}.",
                evidence=[_ptr(f, name_b, f, kind="file")],
                limitation="Cannot tell whether the file was withheld on purpose or lost in packaging.",
                repair=dict(action="flag_for_review", ids=[], file=f, why=f"Confirm whether {f} should be present.")))
    return events


def _rerun(ref, dir_a, dir_b, aid):
    """Run the organizers' analysis on both releases. Returns (before, after) without sample id lists."""
    fn = {"A1": lambda c, p: ref.a1(c, p), "A2": lambda c, p: ref.a2(c)}[aid]
    out = []
    for d in (dir_a, dir_b):
        c, p = ref.load(d)
        r = fn(c, p)
        r.pop("sample_ids", None)
        out.append(r)
    return out


def analyze_releases(release_a: str, release_b: str, output_path: str, *,
                     release_names: tuple[str, str] | None = None, progress=None) -> dict:
    dir_a, dir_b = Path(release_a), Path(release_b)
    name_a, name_b = release_names or (dir_a.name, dir_b.name)
    say = progress or (lambda m: None)

    say(f"Comparing {name_a} and {name_b} (unchanged files are skipped)")
    fn_a, fn_b = _filenames(dir_a), _filenames(dir_b)
    _, _, raw, imp = compare(dir_a, dir_b)

    events = _events(raw, fn_a, fn_b, name_a, name_b)

    findings, repairs = [], []
    for n, ev in enumerate(events, 1):
        fid = f"F{n:02d}"
        idset = set(ev["ids"])
        affects, not_affects, why = [], [], {}
        for aid, res in imp.items():
            if idset:
                hit = sorted(idset & set(res["sample_ids"]))
                hit_flag = bool(hit) and ev["file"] in ANALYSIS_FILES.get(aid, set())
                why[aid] = (f"{len(hit)} of this finding's samples sit inside the slice {aid} reads" if hit_flag
                            else f"none of this finding's samples are inside the slice {aid} reads"
                                 f" (or the file is not an input of {aid})")
            else:  # file-level finding
                hit_flag = res["affected"] and ev["file"] in ANALYSIS_FILES.get(aid, set())
                why[aid] = f"{ev['file']} is {'an input' if hit_flag else 'not an input'} of {aid}"
            (affects if hit_flag else not_affects).append(aid)
        sev = ev["severity_hi"] if affects else ev["severity_lo"]
        findings.append({
            "id": fid, "kind": ev["kind"], "summary": ev["summary"], "severity": sev, "confidence": ev["confidence"],
            "evidence": ev["evidence"][:MAX_EVIDENCE],
            "affects_analyses": affects, "not_affected_analyses": not_affects,
            "limitation": ev["limitation"], "needs_human_review": sev in ("high", "medium"),
            "impact_reasons": why,
        })
        r = ev["repair"]
        targets = [_ptr(i, name_b, r["file"]) for i in r["ids"]][:MAX_EVIDENCE] or [_ptr(r["file"], name_b, r["file"], kind="file")]
        repairs.append({"id": f"R{n:02d}", "action": r["action"], "targets": targets,
                        "justification": r["why"] + " Proposal only; no release file is modified.",
                        "addresses": [fid]})

    say("Rerunning affected analyses only")
    ref = _ref()
    analyses, rerun_failed = [], False
    for aid, res in imp.items():
        triggered = [f["id"] for f in findings if aid in f["affects_analyses"]]
        entry = {"id": aid, "triggered_by": triggered, "reads": ANALYSES[aid]["reads"]}
        if not res["affected"] and not triggered:
            entry.update(status="not_rerun", reason=f"Left alone: {res['reason']}")
        else:
            try:
                before, after = _rerun(ref, dir_a, dir_b, aid)
                entry.update(status="changed" if before != after else "unchanged", before=before, after=after,
                             reason=res["reason"])
            except Exception as e:  # report honestly, never fabricate
                rerun_failed = True
                entry.update(status="not_rerun", reason=f"Cannot rerun: {type(e).__name__}: {e}")
        analyses.append(entry)

    if rerun_failed:
        verdict = "Insufficient Evidence"
    elif any(f["affects_analyses"] for f in findings):
        verdict = "Conditional"
    else:
        verdict = "Ready"

    result = {"findings": findings, "analyses": analyses, "repairs": repairs, "verdict": verdict}
    Path(output_path).write_text(json.dumps(result, indent=2, default=str))
    say(f"Done: {len(findings)} finding(s), verdict {verdict}")
    return result