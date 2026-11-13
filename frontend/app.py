"""Cohort Control Tower — Streamlit dashboard.

Run (from the repository root, with the API already running):
    streamlit run frontend/app.py

All data comes from the FastAPI backend over HTTP (CCT_API_URL, default http://127.0.0.1:8000).
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_client import DEFAULT_URL, ApiClient, ApiError  # noqa: E402

st.set_page_config(page_title="Cohort Control Tower", page_icon="🛰️", layout="wide")

SEV_ICON = {"high": "🔴 high", "medium": "🟠 medium", "low": "🟡 low", "none": "⚪ none"}
VERDICT_STYLE = {
    "Ready": ("success", "Ready: no material change was detected."),
    "Conditional": ("warning", "Conditional: usable only after the flagged items are reviewed."),
    "Blocked": ("error", "Blocked: material changes affect a protected analysis. Do not use release B until a researcher reviews the repairs."),
    "Insufficient Evidence": ("warning", "Insufficient Evidence: the tool could not check enough to support a decision."),
}
KIND_LABEL = {"sample_swap": "Sample swap", "duplicate": "Duplicate profile", "missing_data": "Missing data / coverage",
              "membership_change": "Membership change", "label_conflict": "Label conflict", "join_inflation": "Join inflation",
              "unlinked_record": "Unlinked record", "claim_check": "Claim check", "other": "Other change"}
RECORD_KINDS = ("sample", "patient", "row")
DECISION_ICON = {"approve": "✅ approve", "reject": "❌ reject", "request_more_evidence": "❓ more evidence requested"}


# ----------------------------------------------------------------------------- helpers

def client() -> ApiClient:
    return ApiClient(st.session_state.get("api_url", DEFAULT_URL))


def show_api_error(e: Exception, context: str) -> None:
    if isinstance(e, ApiError):
        code = f" (HTTP {e.status})" if e.status else ""
        st.error(f"{context}{code}: {e.message}")
    else:
        st.error(f"{context}: {type(e).__name__}: {e}")


def ev_table(evidence: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame([{"kind": e.get("kind"), "id": e.get("id"), "release": e.get("release", ""),
                        "file": e.get("file", ""), "note": e.get("note", ""), "url": e.get("url", "")} for e in evidence])
    return df.drop(columns="url") if df.empty or not df["url"].any() else df


def finding_files(f: dict) -> str:
    """The finding's file; engines that don't set `file` name it in each evidence pointer instead."""
    if f.get("file"):
        return f["file"]
    return ", ".join(dict.fromkeys(e["file"] for e in f.get("evidence", []) if e.get("file")))


# ----------------------------------------------------------------------------- sidebar

with st.sidebar:
    st.title("🛰️ Cohort Control Tower")
    st.caption("Track 1 · Cohort Firewall · TCGA-BRCA")
    st.session_state.setdefault("api_url", DEFAULT_URL)
    st.text_input("API URL", key="api_url")
    try:
        h = client().health()
        (st.success if h["status"] == "ok" else st.warning)(f"API {h['status']} · v{h['version']}")
        det = h.get("detector", {})
        dstatus = det.get("status")
        if dstatus == "mock":
            st.error("Detector: **MOCK** (testing only). No detection is performed; results are placeholders.")
        elif dstatus == "not_configured":
            st.error("Detector: **not configured**. Comparisons cannot run until the team engine is connected "
                     "(`CCT_DETECTOR=module:function` or `detection/engine.py`).")
        elif dstatus == "error":
            st.error(f"Detector failed to load: {det.get('error')}")
        else:
            st.success(f"Detector: `{det.get('name')}`" + (" (auto-discovered)" if dstatus == "auto" else ""))
        for p in h.get("problems", []):
            if "MOCK" not in p and "CCT_DETECTOR" not in p:
                st.warning(p)
        API_OK = True
    except Exception as e:  # noqa: BLE001
        show_api_error(e, "API unavailable")
        st.code("uvicorn backend.main:app --port 8000", language="bash")
        API_OK = False
    st.divider()
    st.caption("Research use only. De-identified, patient-derived data. No clinical claims; repairs are proposals and "
               "are never applied automatically.")

st.title("Cohort Control Tower")
st.write("Compare two releases of the TCGA-BRCA research files, see what changed, which analyses it touches, "
         "and export a validated `findings.json` (shared format v0.2).")
if not API_OK:
    st.stop()

# ----------------------------------------------------------------------------- A. dataset selection

st.header("1 · Select releases")
try:
    rels = client().releases()
except Exception as e:  # noqa: BLE001
    show_api_error(e, "Could not list releases")
    st.stop()

if not rels:
    st.error("No releases found. Run `python data/tcga-brca/fetch.py` (baseline) and "
             "`python data/tcga-brca/make_release.py` or `python envelopes/unseal.py ...` for release B.")
names = [r["name"] for r in rels]
by_name = {r["name"]: r for r in rels}

c1, c2 = st.columns(2)
default_a = names.index("baseline") if "baseline" in names else 0
others = [i for i, n in enumerate(names) if n != "baseline"]
default_b = others[-1] if others else 0
rel_a = c1.selectbox("Release A (baseline)", names, index=default_a if names else None)
rel_b = c2.selectbox("Release B (updated)", names, index=default_b if names else None)

if names:
    files = list(by_name[names[0]]["files"].keys())
    table = pd.DataFrame({n: ["✅" if by_name[n]["files"].get(f) else "—" for f in files] for n in (rel_a, rel_b) if n},
                         index=files)
    table.index.name = "file"
    st.dataframe(table, width="stretch")
    meta = pd.DataFrame([{"release": by_name[n]["name"], "origin": by_name[n]["origin"], "location": by_name[n]["location"],
                          "missing required files": ", ".join(by_name[n]["missing_required"]) or "none",
                          "RNA file": "yes" if by_name[n]["has_rna"] else "no (not needed)"} for n in dict.fromkeys((rel_a, rel_b)) if n])
    st.dataframe(meta, hide_index=True, width="stretch")
    for n in dict.fromkeys((rel_a, rel_b)):
        if n and by_name[n]["missing_required"]:
            st.warning(f"{n} is missing {', '.join(by_name[n]['missing_required'])}. The comparison will report it as missing data.")
    if rel_a == rel_b:
        st.info("Release A and B are the same: this is a sanity check and should produce no findings.")

with st.expander("Add a release (upload files or a .zip)"):
    st.caption("For judging day prefer `python envelopes/unseal.py <n> <code words>`: opened envelopes appear "
               "automatically as `envelope-<n>`. Upload is for other test releases.")
    up_name = st.text_input("Name for the uploaded release", placeholder="my-release")
    up_files = st.file_uploader("Release files (clinical.tsv, survival.tsv, *.tsv.gz) or one .zip",
                                accept_multiple_files=True)
    if st.button("Upload release", disabled=not (up_name and up_files)):
        try:
            res = client().upload(up_name, [(f.name, f.getvalue()) for f in up_files])
            st.success(f"Uploaded as `{res['name']}`. Select it above.")
            st.rerun()
        except Exception as e:  # noqa: BLE001
            show_api_error(e, "Upload rejected")

# ----------------------------------------------------------------------------- run

st.header("2 · Run the comparison")
cc1, cc2 = st.columns([1, 2])
engine_ready = det.get("status") in ("configured", "auto", "mock")
if not engine_ready:
    st.error("No detection engine is connected, so **Compare** is disabled. " + (det.get("error") or ""))
if cc1.button("▶ Compare releases", type="primary", disabled=not (rel_a and rel_b and engine_ready)):
    try:
        rec = client().compare(rel_a, rel_b)
        st.session_state["run_id"] = rec["run_id"]
    except Exception as e:  # noqa: BLE001
        show_api_error(e, "Comparison could not start")

try:
    past = client().runs()
except Exception:  # noqa: BLE001
    past = []
if past:
    labels = {r["run_id"]: f"{r['run_id']} · {r['release_a']} → {r['release_b']} · {r['status']}" for r in past}
    current = st.session_state.get("run_id")
    ids = list(labels)
    pick = cc2.selectbox("Or open a previous run", ids, index=ids.index(current) if current in ids else 0,
                         format_func=labels.get)
    if pick != current and cc2.button("Open selected run"):
        st.session_state["run_id"] = pick
        st.rerun()

run_id = st.session_state.get("run_id")
if not run_id:
    st.info("Pick two releases and press **Compare releases**.")
    st.stop()

with st.status(f"Run {run_id}", expanded=True) as status_box:
    deadline = time.time() + 900
    rec = None
    while time.time() < deadline:
        try:
            rec = client().run(run_id)
        except Exception as e:  # noqa: BLE001
            show_api_error(e, "Could not read run status")
            st.stop()
        st.write(f"Status: **{rec['status']}**" + (f" — {rec['progress'][-1].split(' ', 1)[-1]}" if rec.get("progress") else ""))
        if rec["status"] in ("completed", "failed"):
            break
        time.sleep(1.5)
    if rec is None or rec["status"] not in ("completed", "failed"):
        status_box.update(label="Still running — refresh the page to keep watching", state="running")
        st.stop()
    if rec["status"] == "failed":
        status_box.update(label=f"Run {run_id} failed", state="error")
    else:
        status_box.update(label=f"Run {run_id} completed · {rec['release_a']} → {rec['release_b']}", state="complete",
                          expanded=False)

if rec["status"] == "failed":
    st.error(f"The comparison failed: {rec.get('error')}")
    if rec.get("validation") and rec["validation"].get("errors"):
        st.write("Validator output:")
        st.code("\n".join(rec["validation"]["errors"]))
    st.caption("No findings are shown for a failed run; nothing was substituted.")
    st.stop()

try:
    doc, raw_bytes = client().findings(run_id)
except Exception as e:  # noqa: BLE001
    show_api_error(e, "Could not load findings.json")
    st.stop()

summary = rec.get("summary") or {}
findings = doc.get("findings", [])
repairs = doc.get("repairs", [])
analyses = doc.get("analyses", [])
decisions = doc.get("decisions", [])
det = rec.get("detector", {})

# ----------------------------------------------------------------------------- B. overview

st.header("3 · Result")
verdict = doc.get("verdict", "—")
kind, text = VERDICT_STYLE.get(verdict, ("info", verdict))
getattr(st, kind)(f"**Verdict: {verdict}** — {text}")
if summary.get("human_review_required"):
    st.warning(f"⚠️ **Human review required.** {len(summary.get('findings_needing_review', []))} finding(s) and "
               f"{len(repairs)} proposed repair(s) need a researcher's decision. Nothing has been changed in the data.")
if det.get("mock"):
    st.error("⚠️ **MOCK RESULT.** The mock detector produced this run for pipeline testing. Nothing was compared.")
v = rec.get("validation") or {}
st.caption(f"findings.json validated by `{v.get('validator', 'format/validate.py')}`: {'✅ valid' if v.get('valid') else '❌'} · "
           f"engine `{det.get('name')}` · run {run_id}")

ra, rb = summary.get("release_a", {}), summary.get("release_b", {})


def _diff(b, a):
    return (b - a) or None if isinstance(a, int) and isinstance(b, int) else None


st.subheader("Releases")
r1 = st.columns(5)
r1[0].metric(f"Samples in A ({ra.get('name')})", ra.get("samples", "—"),
             help="Unique sample ids across all files in release A (a sample listed in several files counts once).")
r1[1].metric(f"Samples in B ({rb.get('name')})", rb.get("samples", "—"), delta=_diff(rb.get("samples"), ra.get("samples")),
             help="Unique sample ids across all files in release B.")
r1[2].metric("Patients A → B", f"{ra.get('patients', '—')} → {rb.get('patients', '—')}",
             delta=_diff(rb.get("patients"), ra.get("patients")),
             help="Unique patients (first 12 characters of the TCGA barcode).")
r1[3].metric("Samples added / removed (whole release)",
             f"+{summary.get('samples_added', '—')} / −{summary.get('samples_removed', '—')}",
             help="Ids in B but in no file of A / ids in A but in no file of B. A sample dropped from one file but still "
                  "listed in another is NOT counted here; see the next card and the per-file table.")
r1[4].metric("Samples changed in ≥1 file", summary.get("samples_changed_in_any_file", "—"),
             help="Ids added to or removed from at least one individual file (files present in both releases).")

# --- findings breakdown: every kind gets a card, so the cards always add up to the total
kind_counts = Counter(f.get("kind", "other") for f in findings)
sev_counts = Counter(f.get("severity") for f in findings)
review_ids = [f["id"] for f in findings if f.get("needs_human_review")]


def _records(kind: str) -> int:
    return len({e.get("id") for f in findings if f.get("kind", "other") == kind
                for e in f.get("evidence", []) if e.get("kind") in RECORD_KINDS})


st.subheader("Findings")
order = [k for k in KIND_LABEL if kind_counts.get(k)] + sorted(k for k in kind_counts if k not in KIND_LABEL)
cards = [("Total findings", len(findings), "Every finding in findings.json; the cards to the right add up to this.")]
cards += [(KIND_LABEL.get(k, k), kind_counts[k], f"{_records(k)} distinct sample/patient/row id(s) cited as evidence")
          for k in order]
for i in range(0, len(cards), 5):
    row = st.columns(5)
    for col, (label, val, hlp) in zip(row, cards[i:i + 5]):
        col.metric(label, val, help=hlp)
if findings:
    st.caption("By type: " + " + ".join(f"{kind_counts[k]} {KIND_LABEL.get(k, k).lower()}" for k in order)
               + f" = **{len(findings)}** total.")
r3 = st.columns(5)
for col, s in zip(r3, ["high", "medium", "low", "none"]):
    col.metric(f"Severity: {SEV_ICON[s]}", sev_counts.get(s, 0))
r3[4].metric("Need human review", len(review_ids), help=", ".join(review_ids) or None)

an_status = Counter(a.get("status") for a in analyses)
r4 = st.columns(5)
r4[0].metric("Analyses changed", an_status.get("changed", 0), help=", ".join(a["id"] for a in analyses if a.get("status") == "changed") or None)
r4[1].metric("Analyses unchanged after rerun", an_status.get("unchanged", 0))
r4[2].metric("Analyses not rerun", an_status.get("not_rerun", 0))
r4[3].metric("Proposed repairs", len(repairs))
r4[4].metric("Reviewer decisions", len(decisions))

files_tbl = summary.get("files") or {}
if files_tbl:
    ft = pd.DataFrame([{"file": f, "samples A": d.get("samples_a"), "samples B": d.get("samples_b"),
                        "added": d.get("added"), "removed": d.get("removed"),
                        "same count, different members": "⚠️ yes" if d.get("count_equal_membership_differs") else "",
                        "read error": d.get("error") or ""}
                       for f, d in files_tbl.items()])
    if not ft["read error"].any():
        ft = ft.drop(columns="read error")
    st.subheader("Sample ids per file (from the release files' headers)")
    st.dataframe(ft, hide_index=True, width="stretch")
    st.caption("Blank added/removed means the file is missing or unreadable in one of the releases.")
    if any(d.get("count_equal_membership_differs") for d in files_tbl.values()):
        st.warning("At least one file has the **same sample count but different members**. Equal counts do not mean equal data.")
    for f, d in files_tbl.items():
        if d.get("error"):
            st.error(f"{f} could not be read: {d['error']}")
for n in summary.get("notes", []):
    st.caption(f"ℹ️ {n}")
st.caption("Finding counts are tallied from the engine's findings.json (by kind, severity and evidence pointers); sample counts "
           "come from the ids listed in each file. The dashboard performs no detection or analysis of its own.")

# ----------------------------------------------------------------------------- tabs

t_find, t_an, t_rep, t_prov, t_json = st.tabs(
    ["🔎 Findings", "📊 Analysis impact", "🛠️ Repairs & review", "🔐 Provenance", "{ } findings.json"])

repairs_by_finding: dict[str, list[dict]] = {}
for r in repairs:
    for fid in r.get("addresses", []):
        repairs_by_finding.setdefault(fid, []).append(r)
decisions_by_repair: dict[str, list[dict]] = {}
for d in decisions:
    decisions_by_repair.setdefault(d.get("repair_id"), []).append(d)


def repair_label(r: dict) -> str:
    ds = decisions_by_repair.get(r["id"], [])
    return f"{r['id']} {r['action']}" + (f" ({ds[-1]['decision']})" if ds else "")


with t_find:
    if not findings:
        st.info("The engine reported no findings for this pair of releases.")
    else:
        fc = st.columns([1, 1, 1, 1, 2])
        sev_f = fc[0].multiselect("Severity", ["high", "medium", "low", "none"], default=[])
        kinds = sorted({f.get("kind", "other") for f in findings})
        kind_f = fc[1].multiselect("Type", kinds, default=[], format_func=lambda k: KIND_LABEL.get(k, k))
        conf_f = fc[2].multiselect("Confidence", ["high", "medium", "low"], default=[])
        an_f = fc[3].multiselect("Affects analysis", sorted({a for f in findings for a in f.get("affects_analyses", [])}))
        q = fc[4].text_input("Search (summary, record id, file)")
        review_only = st.checkbox("Only findings that need human review")

        def keep(f):
            if sev_f and f.get("severity") not in sev_f:
                return False
            if kind_f and f.get("kind", "other") not in kind_f:
                return False
            if conf_f and f.get("confidence") not in conf_f:
                return False
            if an_f and not set(an_f) & set(f.get("affects_analyses", [])):
                return False
            if review_only and not f.get("needs_human_review"):
                return False
            if q:
                hay = " ".join([f.get("summary", ""), f.get("id", ""), finding_files(f), f.get("claim_text", ""),
                                *(e.get("id", "") for e in f.get("evidence", []))]).lower()
                return q.lower() in hay
            return True

        shown = [f for f in findings if keep(f)]
        st.caption(f"Showing **{len(shown)} of {len(findings)}** findings" +
                   (" (filters active)." if len(shown) != len(findings) else "."))
        has_claims = any(f.get("claim_text") for f in findings)

        def row(f):
            recs = list(dict.fromkeys(e["id"] for e in f["evidence"] if e.get("kind") in RECORD_KINDS))
            out = {
                "id": f["id"], "type": KIND_LABEL.get(f.get("kind"), f.get("kind") or "Other change"),
                "severity": SEV_ICON.get(f["severity"]), "confidence": f["confidence"], "file": finding_files(f),
                "summary": f["summary"], "records": len(recs),
                "affected records": ", ".join(recs[:4]) + (" …" if len(recs) > 4 else ""),
                "evidence items": len(f["evidence"]),
                "affects": ", ".join(f.get("affects_analyses", [])) or "—",
                "not affected": ", ".join(f.get("not_affected_analyses", [])) or "—",
                "repair": ", ".join(repair_label(r) for r in repairs_by_finding.get(f["id"], [])) or "—",
                "review": "⚠️" if f.get("needs_human_review") else ""}
            if has_claims:
                out |= {"claim": f.get("claim_text", ""), "claim verdict": f.get("claim_verdict", ""),
                        "correct value": f.get("correct_value", "")}
            return out

        df = pd.DataFrame([row(f) for f in shown])
        if not df.empty:
            st.dataframe(df, hide_index=True, width="stretch",
                         column_config={"records": st.column_config.NumberColumn(help="Distinct sample/patient/row ids cited"),
                                        "evidence items": st.column_config.NumberColumn(help="All evidence pointers, any kind")})
        st.subheader("Inspect a finding")
        fid = st.selectbox("Finding", [f["id"] for f in shown],
                           format_func=lambda i: next(f"{i} · {f['summary'][:110]}" for f in shown if f["id"] == i))
        f = next((x for x in shown if x["id"] == fid), None)
        if f:
            st.markdown(f"**{f['id']} · {KIND_LABEL.get(f.get('kind'), f.get('kind') or 'Other change')}** — severity {SEV_ICON.get(f['severity'])}, "
                        f"confidence **{f['confidence']}**" + (" · ⚠️ needs human review" if f.get("needs_human_review") else ""))
            if finding_files(f):
                st.caption(f"File(s): {finding_files(f)}")
            st.write(f["summary"])
            if f.get("claim_text"):
                st.markdown(f"**Claim:** {f['claim_text']}  \n**Verdict:** {f.get('claim_verdict', '—')}"
                            + (f"  \n**What the data shows:** {f['correct_value']}" if f.get("correct_value") else ""))
            st.markdown(f"**Evidence** ({len(f['evidence'])} pointer(s); each points to a record in a named release and file)")
            st.dataframe(ev_table(f["evidence"]), hide_index=True, width="stretch")
            ci = st.columns(2)
            ci[0].markdown("**Affects:** " + (", ".join(f.get("affects_analyses", [])) or "none"))
            ci[1].markdown("**Not affected:** " + (", ".join(f.get("not_affected_analyses", [])) or "none"))
            for a, why in (f.get("impact_reasons") or {}).items():
                st.caption(f"{a}: {why}")
            if f.get("limitation"):
                st.info(f"**Limitation:** {f['limitation']}")
            for r in repairs_by_finding.get(f["id"], []):
                st.warning(f"**Proposed repair {r['id']} · {r['action']}** — {r['justification']}")
                for d in decisions_by_repair.get(r["id"], []):
                    st.caption(f"Reviewer ({d.get('reviewer_role')}): {DECISION_ICON.get(d['decision'], d['decision'])} — {d.get('reason')}")
            if f.get("details"):
                with st.expander("Engine details"):
                    st.json(f["details"], expanded=False)

def flatten_result(d: dict) -> dict:
    """Analysis result -> {row label: value}. Nested dicts (e.g. A2 counts / percent per subtype) become one row per key;
    lists (input file names, excluded ids) are joined so nothing the engine returned is dropped."""
    out = {}
    for k, v in d.items():
        if k in ("analysis", "note", "excluded"):
            continue
        if isinstance(v, dict):
            for kk, vv in v.items():
                out[f"{k} · {kk}"] = vv
        elif isinstance(v, list):
            out[k] = ", ".join(map(str, v))
        else:
            out[k] = v
    return out


with t_an:
    if not analyses:
        st.info("The engine returned no `analyses` block (A1/A2 status and before/after results come from the detection engine).")
    else:
        st.dataframe(pd.DataFrame([{
            "analysis": a["id"] + (f" · {a['title']}" if a.get("title") else ""),
            "status": a.get("status"), "rerun": "yes" if a.get("status") in ("changed", "unchanged") else "no",
            "triggered by": ", ".join(map(str, a.get("triggered_by", []))) or "—",
            "reads": a.get("reads") or ", ".join(a.get("inputs") or (a.get("before") or {}).get("inputs") or []) or "—"}
            for a in analyses]), hide_index=True, width="stretch")
    for a in analyses:
        status = a.get("status")
        badge = {"changed": "🔴 changed", "unchanged": "🟢 unchanged after rerun", "not_rerun": "⚪ not rerun"}.get(status, status)
        st.subheader(f"{a['id']}{' · ' + a['title'] if a.get('title') else ''} — {badge}")
        inputs = a.get("inputs") or (a.get("before") or {}).get("inputs") or (a.get("after") or {}).get("inputs")
        st.caption((f"Inputs: {', '.join(inputs)} · " if inputs else "") +
                   f"Rerun: {'yes' if status in ('changed', 'unchanged') else 'no'}"
                   + (f" · Triggered by: {', '.join(map(str, a['triggered_by']))}" if a.get("triggered_by") else ""))
        if a.get("reads"):
            st.caption(f"Reads: {a['reads']}")
        if a.get("reason"):
            st.write(a["reason"])
        cols = [("Before (A)", a.get("before")), ("After (B)", a.get("after")),
                ("B with proposed exclusions (preview)", a.get("after_excluding_flagged"))]
        cols = [(t, flatten_result(d)) for t, d in cols if d]
        if cols:
            keys = list(dict.fromkeys(k for _, d in cols for k in d if k != "inputs"))
            tbl = pd.DataFrame({t: [d.get(k) for k in keys] for t, d in cols}, index=keys, dtype=object)
            if "Before (A)" in tbl and "After (B)" in tbl:
                def _delta(r):
                    x, y = r["Before (A)"], r["After (B)"]
                    if x is None or y is None:
                        return "only in B" if x is None else "only in A"
                    if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
                        return f"{round(y - x, 3):+g}" if y != x else "0"
                    return "" if x == y else "changed"
                tbl["Δ (B − A)"] = tbl.apply(_delta, axis=1)
            tbl.index.name = "result"
            st.dataframe(tbl.map(lambda v: "—" if v is None else str(v)), width="stretch")
        cmp = a.get("comparison")
        if cmp:
            if cmp.get("inputs_added") or cmp.get("inputs_removed"):
                st.write(f"Input samples added: {len(cmp.get('inputs_added', []))} · removed: {len(cmp.get('inputs_removed', []))}")
                with st.expander("Which input samples moved"):
                    st.write({"added": cmp.get("inputs_added", []), "removed": cmp.get("inputs_removed", [])})
            extra = {k: v for k, v in cmp.items() if k not in ("inputs_added", "inputs_removed")}
            if extra:
                st.json(extra, expanded=False)
        if (a.get("after_excluding_flagged") or {}).get("excluded"):
            st.caption("Preview excludes: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in a["after_excluding_flagged"]["excluded"].items()))
        if a.get("before_error"):
            st.error(a["before_error"])
        st.divider()

with t_rep:
    if repairs:
        st.warning("⚠️ **Review required.** These are proposals. The tool never edits a release; a researcher must "
                   "approve, reject or request more evidence (e.g. in a Repair Review Desk) before anything changes.")
        act = Counter(r["action"] for r in repairs)
        st.caption("By action: " + " · ".join(f"{n} {k}" for k, n in act.most_common()) + f" = **{len(repairs)}** repairs.")
        st.dataframe(pd.DataFrame([{
            "id": r["id"], "action": r["action"], "resolves": ", ".join(r.get("addresses", [])),
            "targets": len(r.get("targets", [])),
            "decision": ", ".join(DECISION_ICON.get(d["decision"], d["decision"]) for d in decisions_by_repair.get(r["id"], []))
                        or "pending"} for r in repairs]), hide_index=True, width="stretch")
        for r in repairs:
            with st.container(border=True):
                st.markdown(f"**{r['id']} · {r['action']}** — resolves {', '.join(r.get('addresses', []))} · "
                            f"{len(r.get('targets', []))} target(s)")
                st.write(r["justification"])
                st.dataframe(ev_table(r.get("targets", [])), hide_index=True, width="stretch")
                for d in decisions_by_repair.get(r["id"], []):
                    st.markdown(f"Reviewer decision: **{DECISION_ICON.get(d['decision'], d['decision'])}** "
                                f"by {d.get('reviewer_role', '?')} — {d.get('reason', '')}"
                                + ("" if d.get("original_preserved") is None else
                                   f" · original preserved: {'yes' if d['original_preserved'] else 'no'}"))
    else:
        st.info("No repairs proposed.")
    st.subheader("Reviewer decisions")
    if decisions:
        known = {r["id"] for r in repairs}
        st.dataframe(pd.DataFrame([{
            "repair": d.get("repair_id"), "decision": DECISION_ICON.get(d.get("decision"), d.get("decision")),
            "reviewer role": d.get("reviewer_role"), "reason": d.get("reason"),
            "original preserved": {True: "yes", False: "no"}.get(d.get("original_preserved"), "—"),
            "repair exists": "yes" if d.get("repair_id") in known else "⚠️ no"} for d in decisions]),
            hide_index=True, width="stretch")
    else:
        st.caption("No reviewer decisions yet. A Repair Review Desk adds them to findings.json.")

with t_prov:
    data = doc.get("data", {})
    if data.get("dataset"):
        st.markdown(f"**Dataset:** {data['dataset']}")
    for r in data.get("releases", []):
        st.markdown(f"**{r['name']}** {r.get('role', '')} · {len(r.get('files', []))} file(s)")
        st.dataframe(pd.DataFrame(r["files"]), hide_index=True, width="stretch")
    st.caption("Baseline hashes are of the downloaded files (compare with data/tcga-brca/sources.csv); other releases "
               "hash decompressed content for .gz files, the organizers' convention for generated releases.")
    st.markdown(f"**Question:** {doc.get('question', '—')}")
    prod = doc.get("producer", {})
    st.markdown("**Producer:** " + " · ".join(f"{k}: `{v}`" for k, v in prod.items() if not isinstance(v, dict)))
    if prod.get("engine_producer"):
        st.json({"engine_producer": prod["engine_producer"]}, expanded=False)
    if data.get("engine_data"):
        with st.expander("Release data as reported by the engine"):
            st.json(data["engine_data"], expanded=False)
    st.subheader("Run log")
    st.dataframe(pd.DataFrame([{"run": run_id, "status": rec.get("status"), "created": rec.get("created_at"),
                                "started": rec.get("started_at"), "finished": rec.get("finished_at"),
                                "engine": det.get("name"), "engine status": det.get("status")}]),
                 hide_index=True, width="stretch")
    if rec.get("progress"):
        with st.expander(f"Progress messages ({len(rec['progress'])})"):
            st.code("\n".join(rec["progress"]))

with t_json:
    st.json(doc, expanded=False)

st.header("4 · Export")
st.download_button("⬇️ Download findings.json (validated)", data=raw_bytes, file_name=f"findings-{run_id}.json",
                   mime="application/json", type="primary")
st.caption("This is the exact file the backend validated with `python format/validate.py`. Re-check it yourself: "
           f"`python format/validate.py findings-{run_id}.json`")
