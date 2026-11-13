"""Cohort Control Tower — Streamlit dashboard.

Run (from the repository root, with the API already running):
    streamlit run frontend/app.py

All data comes from the FastAPI backend over HTTP (CCT_API_URL, default http://127.0.0.1:8000).
"""
from __future__ import annotations

import os
import sys
import time

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
    return pd.DataFrame([{"kind": e.get("kind"), "id": e.get("id"), "release": e.get("release", ""),
                          "file": e.get("file", ""), "note": e.get("note", "")} for e in evidence])


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

m = summary.get("metrics", {})
ra, rb = summary.get("release_a", {}), summary.get("release_b", {})
r1 = st.columns(4)
r1[0].metric(f"Samples in A ({ra.get('name')})", ra.get("samples", "—"))
r1[1].metric(f"Samples in B ({rb.get('name')})", rb.get("samples", "—"),
             delta=(rb.get("samples", 0) - ra.get("samples", 0)) or None)
r1[2].metric("Samples added (any file)", summary.get("samples_added", "—"))
r1[3].metric("Samples removed (any file)", summary.get("samples_removed", "—"))
r2 = st.columns(4)
r2[0].metric("Sample swaps", m.get("sample_swaps", 0), help=f"{m.get('samples_in_swaps', 0)} samples involved")
r2[1].metric("Duplicate findings", m.get("duplicate_findings", 0), help=f"{m.get('samples_in_duplicates', 0)} samples involved")
r2[2].metric("Missing-data / coverage findings", m.get("missing_data_or_coverage", 0))
r2[3].metric("Total findings", m.get("total_findings", len(findings)))

files_tbl = summary.get("files") or {}
if files_tbl:
    ft = pd.DataFrame([{"file": f, "samples A": d.get("samples_a"), "samples B": d.get("samples_b"),
                        "added": d.get("added"), "removed": d.get("removed"),
                        "same count, different members": "⚠️ yes" if d.get("count_equal_membership_differs") else ""}
                       for f, d in files_tbl.items()])
    st.subheader("Sample ids per file (from the release files' headers)")
    st.dataframe(ft, hide_index=True, width="stretch")
    if any(d.get("count_equal_membership_differs") for d in files_tbl.values()):
        st.warning("At least one file has the **same sample count but different members**. Equal counts do not mean equal data.")
for n in summary.get("notes", []):
    st.caption(f"ℹ️ {n}")
st.caption("Counts above are tallied from the engine's findings (by kind and evidence pointers) and from the ids listed in each file; "
           "the dashboard performs no detection or analysis of its own.")

# ----------------------------------------------------------------------------- tabs

t_find, t_an, t_rep, t_prov, t_json = st.tabs(
    ["🔎 Findings", "📊 Analysis impact", "🛠️ Repairs & review", "🔐 Provenance", "{ } findings.json"])

repairs_by_finding: dict[str, list[dict]] = {}
for r in repairs:
    for fid in r.get("addresses", []):
        repairs_by_finding.setdefault(fid, []).append(r)

with t_find:
    if not findings:
        st.info("The engine reported no findings for this pair of releases.")
    else:
        fc = st.columns([1, 1, 1, 2])
        sev_f = fc[0].multiselect("Severity", ["high", "medium", "low", "none"], default=[])
        kinds = sorted({f.get("kind", "other") for f in findings})
        kind_f = fc[1].multiselect("Type", kinds, default=[], format_func=lambda k: KIND_LABEL.get(k, k))
        an_f = fc[2].multiselect("Affects analysis", sorted({a for f in findings for a in f.get("affects_analyses", [])}))
        q = fc[3].text_input("Search (summary, sample id, file)")

        def keep(f):
            if sev_f and f.get("severity") not in sev_f:
                return False
            if kind_f and f.get("kind") not in kind_f:
                return False
            if an_f and not set(an_f) & set(f.get("affects_analyses", [])):
                return False
            if q:
                hay = (f.get("summary", "") + " " + " ".join(e.get("id", "") for e in f.get("evidence", []))).lower()
                return q.lower() in hay
            return True

        shown = [f for f in findings if keep(f)]
        df = pd.DataFrame([{
            "id": f["id"], "type": KIND_LABEL.get(f.get("kind"), f.get("kind")), "severity": SEV_ICON.get(f["severity"]),
            "confidence": f["confidence"], "file": f.get("file", ""), "summary": f["summary"],
            "affected records": ", ".join([e["id"] for e in f["evidence"] if e.get("kind") in ("sample", "patient", "row")][:4])
                                + (" …" if sum(e.get("kind") in ("sample", "patient", "row") for e in f["evidence"]) > 4 else ""),
            "affects": ", ".join(f.get("affects_analyses", [])) or "—",
            "not affected": ", ".join(f.get("not_affected_analyses", [])) or "—",
            "repair": ", ".join(f"{r['id']} {r['action']}" for r in repairs_by_finding.get(f["id"], [])) or "—",
            "review": "⚠️" if f.get("needs_human_review") else ""} for f in shown])
        st.dataframe(df, hide_index=True, width="stretch")
        st.subheader("Inspect a finding")
        fid = st.selectbox("Finding", [f["id"] for f in shown],
                           format_func=lambda i: next(f"{i} · {f['summary'][:110]}" for f in shown if f["id"] == i))
        f = next((x for x in shown if x["id"] == fid), None)
        if f:
            st.markdown(f"**{f['id']} · {KIND_LABEL.get(f.get('kind'), f.get('kind'))}** — severity {SEV_ICON.get(f['severity'])}, "
                        f"confidence **{f['confidence']}**" + (" · ⚠️ needs human review" if f.get("needs_human_review") else ""))
            st.write(f["summary"])
            st.markdown("**Evidence** (each row points to a record in a named release and file)")
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
            if f.get("details"):
                with st.expander("Engine details"):
                    st.json(f["details"], expanded=False)

with t_an:
    if not analyses:
        st.info("The engine returned no `analyses` block (A1/A2 status and before/after results come from the detection engine).")
    for a in analyses:
        status = a.get("status")
        badge = {"changed": "🔴 changed", "unchanged": "🟢 unchanged after rerun", "not_rerun": "⚪ not rerun"}.get(status, status)
        st.subheader(f"{a['id']}{' · ' + a['title'] if a.get('title') else ''} — {badge}")
        st.caption((f"Inputs: {', '.join(a['inputs'])} · " if a.get("inputs") else "") +
                   f"Rerun: {'yes' if status in ('changed', 'unchanged') else 'no'}"
                   + (f" · Triggered by: {', '.join(map(str, a['triggered_by']))}" if a.get("triggered_by") else ""))
        if a.get("reason"):
            st.write(a["reason"])
        cols = [("Before (A)", a.get("before")), ("After (B)", a.get("after")),
                ("B with proposed exclusions (preview)", a.get("after_excluding_flagged"))]
        cols = [(t, d) for t, d in cols if d]
        if cols:
            keys = []
            for _, d in cols:
                for k, v in d.items():
                    if k not in keys and not isinstance(v, (dict, list)) and k not in ("analysis", "note", "excluded"):
                        keys.append(k)
            tbl = pd.DataFrame({t: [d.get(k) for k in keys] for t, d in cols}, index=keys).astype(str)
            st.dataframe(tbl, width="stretch")
            for t, d in cols:
                for k, v in d.items():
                    if isinstance(v, dict) and k != "excluded":
                        st.caption(f"{t} · {k}: " + ", ".join(f"{kk} {vv}" for kk, vv in v.items()))
        cmp = a.get("comparison")
        if cmp:
            if cmp.get("inputs_added") or cmp.get("inputs_removed"):
                st.write(f"Input samples added: {len(cmp['inputs_added'])} · removed: {len(cmp['inputs_removed'])}")
                with st.expander("Which input samples moved"):
                    st.write({"added": cmp["inputs_added"], "removed": cmp["inputs_removed"]})
        if a.get("after_excluding_flagged", {}).get("excluded"):
            st.caption("Preview excludes: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in a["after_excluding_flagged"]["excluded"].items()))
        if a.get("before_error"):
            st.error(a["before_error"])
        st.divider()

with t_rep:
    if repairs:
        st.warning("⚠️ **Review required.** These are proposals. The tool never edits a release; a researcher must "
                   "approve, reject or request more evidence (e.g. in a Repair Review Desk) before anything changes.")
        for r in repairs:
            with st.container(border=True):
                st.markdown(f"**{r['id']} · {r['action']}** — resolves {', '.join(r.get('addresses', []))}")
                st.write(r["justification"])
                st.dataframe(ev_table(r.get("targets", [])), hide_index=True, width="stretch")
    else:
        st.info("No repairs proposed.")

with t_prov:
    for r in doc.get("data", {}).get("releases", []):
        st.markdown(f"**{r['name']}** {r.get('role', '')}")
        st.dataframe(pd.DataFrame(r["files"]), hide_index=True, width="stretch")
    st.caption("Baseline hashes are of the downloaded files (compare with data/tcga-brca/sources.csv); other releases "
               "hash decompressed content for .gz files, the organizers' convention for generated releases.")
    st.json({"producer": doc.get("producer"), "question": doc.get("question")}, expanded=False)

with t_json:
    st.json(doc, expanded=False)

st.header("4 · Export")
st.download_button("⬇️ Download findings.json (validated)", data=raw_bytes, file_name=f"findings-{run_id}.json",
                   mime="application/json", type="primary")
st.caption("This is the exact file the backend validated with `python format/validate.py`. Re-check it yourself: "
           f"`python format/validate.py findings-{run_id}.json`")
