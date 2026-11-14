"""Cohort Control Tower — Streamlit dashboard (v5).

Run (from the repository root, with the API already running):
    streamlit run frontend/app.py
Single-command hosts (Streamlit Community Cloud): run the same command without the API; the dashboard starts
`uvicorn backend.main:app` itself as a sidecar process (frontend/local_backend.py) and fetches the official
data on first start. See frontend/README.md, "Deploy as a website".

Layout
  Top bar      project name · Home | Runs | Engine | About · theme switch · API/engine status
  Home, left   one work panel with a tab per job:
                 Select release  pick A and B, start the comparison
                 Results         what changed: counts, analysis impact, findings (read-only)
                 Next steps      what to do: fixes that need typed input, items for a researcher, export
                 Detailed info   provenance: run facts, per-file membership, checksums, raw output
                 Assistant       questions about the run, answered from findings.json (detection/qa.py)
  Home, right  side panel: quick summary, live workflow while comparing, one-click fixes

All data comes from the FastAPI backend over HTTP; the dashboard computes no findings itself.
The fix endpoints (/api/runs/{id}/fixes) are optional: without them, fixes are staged in the browser session and
labelled as such. Q&A uses GET /api/qa/chips and POST /api/runs/{id}/ask; typed questions need a model configured on
the backend (.env: LLM_BASE_URL + OPENAI_MODEL for a local Ollama model, or OPENAI_API_KEY).
"""
from __future__ import annotations

import html
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_client import DEFAULT_URL, ApiClient, ApiError  # noqa: E402
import local_backend  # noqa: E402

st.set_page_config(page_title="Cohort Control Tower", page_icon="🛰️", layout="wide",
                   initial_sidebar_state="collapsed")

# ============================================================================= theme
THEMES = {
    "dark": dict(page="#171311", bar="#241c18", bar_text="#f1e8dd", bar_muted="#b39d88",
                 panel="#211a16", side="#272019", sub="#2d2521", line="#433730", ink="#efe6dc", muted="#a8988a",
                 accent="#d08a43", ok="#8cc08a", warn="#e3aa5e", bad="#e5806a",
                 ok_bg="#24382a", warn_bg="#3f3020", bad_bg="#45261f", muted_bg="#352d28",
                 input_bg="#2f2622", input_text="#f1e8dd", btn_text="#1a120c"),
    "light": dict(page="#e7e0d6", bar="#3f322a", bar_text="#f4ede4", bar_muted="#c7b6a4",
                  panel="#f3eee8", side="#ece5dc", sub="#faf7f3", line="#d3c6b7", ink="#2a221c", muted="#6f6258",
                  accent="#9a5b22", ok="#3a7442", warn="#8f611a", bad="#9a3a2a",
                  ok_bg="#dcebdc", warn_bg="#f3e5c9", bad_bg="#f2ddd6", muted_bg="#e6ded3",
                  input_bg="#ffffff", input_text="#2a221c", btn_text="#fff8f0"),
}

CSS = """
<style>
:root { __VARS__ }
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] { background: var(--page) !important; color: var(--ink); }
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none !important; }
.block-container { padding: .8rem 1.6rem 1.2rem; max-width: 100% !important; }
h1, h2, h3, h4, h5, p, li, span, label, .stMarkdown { color: var(--ink); }
[data-testid="stWidgetLabel"] p { color: var(--muted) !important; font-size: .82rem; font-weight: 600; }
code { color: var(--accent); background: var(--sub); }

/* ---- inputs (react-aria widgets in Streamlit 1.6x): one surface, no dark blocks */
[data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"],
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-testid="stChatInput"] textarea,
[data-testid="stTextInput"] > div > div, [data-testid="stChatInput"] > div {
  background: var(--input-bg) !important; color: var(--input-text) !important; border-color: var(--line) !important; }
[data-testid="stSelectbox"] [role="group"] *, [data-testid="stMultiSelect"] [role="group"] * {
  background: transparent !important; color: var(--input-text) !important; }
[data-testid="stSelectbox"] input::placeholder, [data-testid="stTextInput"] input::placeholder,
[data-testid="stChatInput"] textarea::placeholder { color: var(--muted) !important; opacity: 1; }
[role="listbox"], [role="listbox"] [role="option"] { background: var(--input-bg) !important; color: var(--input-text) !important; }
[role="listbox"] [role="option"]:hover, [role="listbox"] [role="option"][data-focused="true"] { background: var(--sub) !important; }
[data-testid="stExpander"] details { background: transparent; border: 1px solid var(--line) !important; border-radius: 8px; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: var(--ink) !important; font-size: .9rem; }
[data-testid="stFileUploaderDropzone"] { background: var(--sub) !important; border-color: var(--line) !important; }
[data-testid="stFileUploaderDropzone"] * { color: var(--ink) !important; }
.stButton > button, .stDownloadButton > button {
  background: var(--sub); color: var(--ink); border: 1px solid var(--line); border-radius: 7px; font-weight: 600; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color: var(--accent); color: var(--accent); }
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] { background: var(--accent); border-color: var(--accent); }
.stButton > button *, .stDownloadButton > button * { color: inherit !important; }
.stButton > button[kind="primary"] *, .stDownloadButton > button[kind="primary"] * { color: var(--btn-text) !important; }
.stButton > button[kind="tertiary"] { background: transparent; border: none; color: var(--accent); padding: 0 .2rem; min-height: 0; }
.stButton > button:disabled { opacity: .45; }
[data-testid="stJson"] { background: var(--sub); border-radius: 6px; }
pre, [data-testid="stCode"] pre { background: var(--sub) !important; color: var(--ink) !important; }
[data-testid="stChatMessage"] { background: var(--sub); border-radius: 10px; }
[data-testid="stToast"] { background: var(--sub) !important; color: var(--ink) !important; }

/* ---- top bar */
.st-key-topbar { background: var(--bar); border-radius: 10px; padding: .55rem 1.3rem; margin-bottom: .9rem; }
.st-key-topbar .brand { color: var(--bar-text); font-size: 1.45rem; font-weight: 700; white-space: nowrap; line-height: 1.2; }
.st-key-topbar .brand small { display: block; color: var(--bar-muted); font-weight: 400; font-size: .78rem; letter-spacing: .03em; }
.st-key-topbar .stButton > button { background: transparent; border: 1px solid transparent; width: 100%; min-height: 2.5rem; }
.st-key-topbar .stButton > button * { color: var(--bar-text) !important; font-size: 1.02rem !important; font-weight: 700; }
.st-key-topbar .stButton > button:hover { border-color: var(--bar-muted); }
.st-key-topbar .stButton > button[kind="primary"] { background: var(--accent); border-color: var(--accent); }
.st-key-topbar .stButton > button[kind="primary"] * { color: var(--btn-text) !important; }
.st-key-topbar .status { color: var(--bar-muted); font-size: .86rem; text-align: right; white-space: nowrap; }
.dot { display: inline-block; width: .55rem; height: .55rem; border-radius: 50%; margin-right: .4rem; vertical-align: middle; }
.dot.ok { background: var(--ok); } .dot.warn { background: var(--warn); } .dot.bad { background: var(--bad); }

/* ---- panels */
.st-key-main, .st-key-side, .st-key-page { border-radius: 12px; padding: .9rem 1.3rem 1.2rem; border: 1px solid var(--line); }
.st-key-main, .st-key-page { background: var(--panel); }
.st-key-side { background: var(--side); }
[class*="st-key-card-"] { background: var(--sub); border: 1px solid var(--line); border-radius: 10px; padding: .75rem 1rem .6rem; }
[class*="st-key-card-"].sev-high { border-left: 4px solid var(--bad); }

/* ---- tabs (Streamlit 1.6x: data-testid="stTab") */
[data-testid="stTabs"] [role="tablist"] { justify-content: center; gap: .35rem; border-bottom: 1px solid var(--line); }
[data-testid="stTab"] { padding: .7rem 1.5rem !important; border-radius: 9px 9px 0 0; }
[data-testid="stTab"] p { font-size: 1.08rem !important; font-weight: 700 !important; color: var(--muted) !important; }
[data-testid="stTab"][aria-selected="true"] { background: var(--sub); }
[data-testid="stTab"][aria-selected="true"] p { color: var(--accent) !important; }
[data-testid="stTab"]:hover p { color: var(--ink) !important; }
[data-testid="stTabs"] .react-aria-SelectionIndicator { background: var(--accent) !important; height: 3px; }

/* ---- building blocks */
.sec { display: flex; align-items: baseline; gap: .7rem; margin: .9rem 0 .45rem; }
.sec .t { font-size: 1.08rem; font-weight: 700; color: var(--ink); }
.sec .h { font-size: .82rem; color: var(--muted); }
.hint { font-size: .82rem; color: var(--muted); margin: .15rem 0 .4rem; line-height: 1.4; }
.chip { display: inline-block; border-radius: 999px; padding: .08rem .55rem; font-size: .76rem; font-weight: 700; margin: 0 .25rem .2rem 0;
        background: var(--muted-bg); color: var(--muted); max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: middle; }
.chip.ok { background: var(--ok-bg); color: var(--ok); } .chip.warn { background: var(--warn-bg); color: var(--warn); }
.chip.bad { background: var(--bad-bg); color: var(--bad); } .chip.accent { background: var(--warn-bg); color: var(--accent); }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .86rem; }
.muted { color: var(--muted); }
.notice { border-left: 3px solid var(--line); background: var(--sub); border-radius: 0 6px 6px 0; padding: .45rem .8rem; margin: .3rem 0 .5rem; font-size: .9rem; color: var(--ink); }
.notice.ok { border-left-color: var(--ok); } .notice.warn { border-left-color: var(--warn); } .notice.bad { border-left-color: var(--bad); }

.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: .6rem; margin: .2rem 0 .4rem; }
.stats.two { grid-template-columns: 1fr 1fr; }
.stat { background: var(--sub); border: 1px solid var(--line); border-radius: 9px; padding: .6rem .85rem; }
.stat .k { font-size: .72rem; text-transform: uppercase; letter-spacing: .07em; color: var(--muted); }
.stat .v { font-size: 1.45rem; font-weight: 700; color: var(--ink); line-height: 1.25; margin: .1rem 0; overflow-wrap: anywhere; }
.stat .s { font-size: .8rem; color: var(--muted); line-height: 1.35; }
.stat.ok .v { color: var(--ok); } .stat.warn .v { color: var(--warn); } .stat.bad .v { color: var(--bad); }

/* vertical lists: one row per item, label left, value right */
.list { border: 1px solid var(--line); border-radius: 8px; overflow: hidden; margin: .2rem 0 .5rem; }
.list .row { display: flex; gap: .8rem; align-items: baseline; justify-content: space-between; padding: .42rem .75rem;
             border-bottom: 1px solid var(--line); font-size: .9rem; }
.list .row:last-child { border-bottom: none; }
.list .row:nth-child(even) { background: rgba(127,127,127,.05); }
.list .row .l { color: var(--ink); min-width: 0; overflow-wrap: anywhere; }
.list .row .r { color: var(--ink); text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.list .row .sub { display: block; color: var(--muted); font-size: .8rem; white-space: normal; }
.list.scroll { max-height: 320px; overflow-y: auto; }

.fhead { display: flex; flex-wrap: wrap; align-items: center; gap: .1rem; }
.fhead .id { font-weight: 700; margin-right: .45rem; color: var(--ink); }
.fsum { margin: .35rem 0 .15rem; font-size: .95rem; line-height: 1.45; }
.fmeta { font-size: .8rem; color: var(--muted); }

/* workflow stepper */
.steps { margin: .2rem 0 .3rem; }
.step { display: flex; gap: .6rem; align-items: flex-start; padding: .32rem 0; }
.step .i { flex: 0 0 1.35rem; height: 1.35rem; border-radius: 50%; display: flex; align-items: center; justify-content: center;
           font-size: .75rem; font-weight: 700; border: 1.5px solid var(--line); color: var(--muted); }
.step.done .i { background: var(--ok-bg); border-color: var(--ok); color: var(--ok); }
.step.active .i { border-color: var(--accent); color: var(--accent); animation: pulse 1.4s infinite; }
.step.fail .i { background: var(--bad-bg); border-color: var(--bad); color: var(--bad); }
.step .t { font-size: .9rem; color: var(--ink); line-height: 1.35; }
.step.todo .t { color: var(--muted); }
.step .t small { display: block; color: var(--muted); font-size: .78rem; overflow-wrap: anywhere; }
@keyframes pulse { 50% { opacity: .35; } }

.fixrow { font-size: .86rem; line-height: 1.3; padding-top: .25rem; }
.fixrow .sub { display: block; font-size: .76rem; color: var(--muted); }
.done-txt { text-decoration: line-through; color: var(--muted); }
.footer { text-align: center; color: var(--muted); font-size: .76rem; margin-top: 1rem; }
</style>
"""

# ============================================================================= vocabulary
VERDICT = {  # css kind, meaning
    "Ready": ("ok", "No material change detected."),
    "Conditional": ("warn", "Usable once the flagged items are reviewed."),
    "Blocked": ("bad", "A protected analysis is affected; do not use release B yet."),
    "Insufficient Evidence": ("warn", "The engine could not check enough to decide."),
}
KIND_LABEL = {"sample_swap": "Sample swap", "duplicate": "Duplicate profile", "missing_data": "Missing data / coverage",
              "membership_change": "Membership change", "label_conflict": "Label conflict", "join_inflation": "Join inflation",
              "unlinked_record": "Unlinked record", "claim_check": "Claim check", "other": "Other change"}
ACTION_LABEL = {"exclude": "Exclude", "relabel": "Relabel", "restore_from_previous_release": "Restore from release A",
                "flag_for_review": "Flag for review", "other": "Other"}
DECISION_LABEL = {"approve": "approved", "reject": "rejected", "request_more_evidence": "more evidence requested"}
SEV_KIND = {"high": "bad", "medium": "warn", "low": "muted", "none": "muted"}
SEV_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3}
RECORD_KINDS = ("sample", "patient", "row")
SIDE_FIX_ROWS = 6  # one-click rows per finding in the side panel; the rest go to Next steps


# ============================================================================= small helpers
def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def chip(kind: str, text, title: str | None = None) -> str:
    t = f' title="{esc(title)}"' if title else ""
    return f'<span class="chip {kind}"{t}>{esc(text)}</span>'


def section(title: str, hint_text: str = "") -> None:
    st.html(f'<div class="sec"><span class="t">{esc(title)}</span>'
            + (f'<span class="h">{esc(hint_text)}</span>' if hint_text else "") + "</div>")


def hint(text: str) -> None:
    st.html(f'<div class="hint">{esc(text)}</div>')


def notice(kind: str, text: str) -> None:
    st.html(f'<div class="notice {kind}">{esc(text)}</div>')


def rows_html(rows: list[tuple[str, str]], scroll: bool = False) -> str:
    """Vertical list: each item is (left html, right html)."""
    body = "".join(f'<div class="row"><span class="l">{l}</span><span class="r">{r}</span></div>' for l, r in rows)
    return f'<div class="list{" scroll" if scroll else ""}">{body}</div>'


def stat(label: str, value, sub: str = "", kind: str = "") -> str:
    return (f'<div class="stat {kind}"><div class="k">{esc(label)}</div><div class="v">{esc(value)}</div>'
            f'<div class="s">{esc(sub)}</div></div>')


def short_engine(name: str | None) -> str:
    if not name:
        return "engine"
    return name.split(":")[0] if ":" in name and not name.startswith("MOCK") else name


def short_hash(h: str | None) -> str:
    return f"{h[:10]}…" if h and len(h) > 12 else (h or "—")


def local_time(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        tz = st.context.timezone
        if tz:
            dt = dt.astimezone(ZoneInfo(tz))
        return dt.strftime("%b %d, %H:%M")
    except Exception:  # noqa: BLE001
        return iso


def api_error_text(e: Exception) -> str:
    if isinstance(e, ApiError):
        return e.message + (f" (HTTP {e.status})" if e.status else "")
    return f"{type(e).__name__}: {e}"


def client() -> ApiClient:
    return ApiClient(st.session_state.get("api_url", DEFAULT_URL))


def records_of(f: dict) -> list[str]:
    return list(dict.fromkeys(e["id"] for e in f.get("evidence", []) if e.get("kind") in RECORD_KINDS))


def finding_file(f: dict) -> str:
    if f.get("file"):
        return f["file"]
    return ", ".join(dict.fromkeys(e["file"] for e in f.get("evidence", []) if e.get("file")))


def flatten_result(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if k in ("analysis", "note", "excluded", "inputs"):
            continue
        if isinstance(v, dict):
            for kk, vv in v.items():
                out[f"{k} · {kk}"] = vv
        elif isinstance(v, list):
            out[k] = ", ".join(map(str, v))
        else:
            out[k] = v
    return out


def analysis_state(a: dict) -> tuple[str, str]:
    s = a.get("status")
    if s == "changed":
        return "bad", "changed · rerun"
    if s == "unchanged":
        return "ok", "unchanged · rerun"
    return "muted", "not rerun"


# ============================================================================= fixes
FIELD_RE = re.compile(r" in (.+)$")


def _fields_from_note(note: str) -> list[str]:
    m = FIELD_RE.search(note or "")
    if not m:
        return []
    txt = re.sub(r"\s*\(\+\d+ more\)", "", m.group(1))
    return [x.strip() for x in txt.split(",") if x.strip()]


def fix_plan(f: dict, repairs: list[dict]) -> dict | None:
    """Which quick fix a finding offers.  {"type": "exclude"|"relabel", "rows": [...]} or None.

    A backend can send `finding["fix"] = {"type": ..., "targets": [{id, file, field, value_a, value_b, note,
    suggested}]}` to control this exactly. Without it: duplicates -> exclude (one click per record),
    label conflicts -> relabel (typed value per record). Everything else stays a proposal for a researcher.
    """
    given = f.get("fix")
    if isinstance(given, dict) and given.get("type") in ("exclude", "relabel"):
        rows = [{"id": t.get("id"), "file": t.get("file") or finding_file(f), "note": t.get("note", ""),
                 "fields": [t["field"]] if t.get("field") else _fields_from_note(t.get("note", "")),
                 "value_a": t.get("value_a"), "value_b": t.get("value_b"), "suggested": t.get("suggested", False)}
                for t in given.get("targets", []) if t.get("id")]
        return {"type": given["type"], "rows": rows} if rows else None
    kind = f.get("kind")
    if kind not in ("duplicate", "label_conflict"):
        return None
    suggested = {t.get("id") for r in repairs if r.get("action") == "exclude" for t in r.get("targets", [])}
    rows, seen = [], set()
    for e in f.get("evidence", []):
        if e.get("kind") not in RECORD_KINDS or e["id"] in seen:
            continue
        seen.add(e["id"])
        rows.append({"id": e["id"], "file": e.get("file") or finding_file(f), "note": e.get("note", ""),
                     "fields": [e["field"]] if e.get("field") else _fields_from_note(e.get("note", "")),
                     "value_a": e.get("value_a"), "value_b": e.get("value_b"), "suggested": e["id"] in suggested})
    if not rows:
        return None
    return {"type": "exclude" if kind == "duplicate" else "relabel", "rows": rows}


def fix_backend_available(run_id: str, features: dict) -> bool:
    if "fixes" in features:
        return bool(features["fixes"])
    key = f"fixapi-{st.session_state['api_url']}"
    if key not in st.session_state:
        try:
            st.session_state[key] = client().fixes(run_id) is not None
        except Exception:  # noqa: BLE001
            st.session_state[key] = False
    return st.session_state[key]


def load_fixes(run_id: str, backend: bool) -> list[dict]:
    if backend:
        try:
            return client().fixes(run_id) or []
        except Exception as e:  # noqa: BLE001
            st.toast(f"Could not load fixes: {api_error_text(e)}")
            return []
    return st.session_state.setdefault("staged_fixes", {}).setdefault(run_id, [])


def apply_fix(run_id: str, backend: bool, body: dict) -> None:
    if backend:
        try:
            client().apply_fix(run_id, body)
        except Exception as e:  # noqa: BLE001
            st.toast(f"Fix not applied: {api_error_text(e)}")
            return
    else:
        staged = st.session_state.setdefault("staged_fixes", {}).setdefault(run_id, [])
        staged.append({"fix_id": f"S{len(staged) + 1:02d}", "status": "staged", **body})
    st.rerun()


def undo_fix(run_id: str, backend: bool, fix_id: str) -> None:
    if backend:
        try:
            client().undo_fix(run_id, fix_id)
        except Exception as e:  # noqa: BLE001
            st.toast(f"Undo failed: {api_error_text(e)}")
            return
    else:
        staged = st.session_state.setdefault("staged_fixes", {}).setdefault(run_id, [])
        staged[:] = [x for x in staged if x.get("fix_id") != fix_id]
    st.rerun()


# ============================================================================= state, theme, health
ss = st.session_state
ss.setdefault("api_url", os.environ.get("CCT_API_URL", DEFAULT_URL))
ss.setdefault("page", "Home")
ss.setdefault("run_id", None)
ss.setdefault("exported", set())
if "theme" not in ss:
    try:
        ss["theme"] = st.context.theme.type if st.context.theme.type in THEMES else "dark"
    except Exception:  # noqa: BLE001
        ss["theme"] = "dark"
T = THEMES[ss["theme"]]
st.html(CSS.replace("__VARS__", " ".join(f"--{k.replace('_', '-')}: {v};" for k, v in T.items())))


@st.cache_data(ttl=5, show_spinner=False)
def fetch_health(url: str) -> dict:
    return ApiClient(url).health()


def resolve_backend() -> tuple[dict | None, str | None]:
    """Find the API. Two-process mode: it is already running at CCT_API_URL. Single-command hosts (Streamlit
    Community Cloud): start the repository's own backend as a sidecar process and talk to it over HTTP.

    CCT_MODE=http     only connect to CCT_API_URL
    CCT_MODE=sidecar  always run `uvicorn backend.main:app` next to the dashboard
    CCT_MODE=auto     connect if reachable, otherwise start the sidecar (default)
    Returns (health, error)."""
    url = ss["api_url"]
    want = local_backend.mode()
    try:
        if want == "http" or (want == "auto" and local_backend.api_alive(url)):
            h = fetch_health(url)
            ss["backend_mode"] = "sidecar" if local_backend.sidecar_pid() else "http"
            return h, None
    except Exception as e:  # noqa: BLE001
        return None, api_error_text(e)
    try:
        if not (local_backend.baseline_ready() and local_backend.practice_ready()):
            with st.status("First start: preparing the official data", expanded=True) as box:
                local_backend.ensure_data(lambda m: box.write(m))
                box.update(label="Data ready", state="complete", expanded=False)
        with st.spinner("Starting the Cohort Control Tower API (uvicorn backend.main:app)"):
            local_backend.ensure_api(url)
        fetch_health.clear()
        h = fetch_health(url)
        ss["backend_mode"] = "sidecar"
        return h, None
    except Exception as e:  # noqa: BLE001
        return None, f"Could not start the backend next to the dashboard: {api_error_text(e)}"


health, health_err = resolve_backend()
det = (health or {}).get("detector", {}) or {}
det_status = det.get("status")
engine_ready = det_status in ("configured", "auto", "mock")
features = (health or {}).get("features") or {}

# ============================================================================= top bar
with st.container(key="topbar"):
    cols = st.columns([2.6, 1, 1, 1, 1, 0.9, 2.2], vertical_alignment="center")
    cols[0].html('<div class="brand">Cohort Control Tower<small>TCGA-BRCA · Cohort Firewall</small></div>')
    for col, name in zip(cols[1:5], ("Home", "Runs", "Engine", "About")):
        if col.button(name, key=f"nav-{name}", width="stretch", type="primary" if ss["page"] == name else "secondary"):
            ss["page"] = name
            st.rerun()
    other = "light" if ss["theme"] == "dark" else "dark"
    if cols[5].button("☀ Light" if other == "light" else "☾ Dark", key="theme-toggle", width="stretch"):
        ss["theme"] = other
        st.rerun()
    if health_err:
        dot, txt = "bad", "backend offline"
    else:
        dot, txt = {"mock": ("warn", "engine: MOCK"), "not_configured": ("bad", "no engine"), "error": ("bad", "engine error"),
                    "auto": ("ok", "engine connected"), "configured": ("ok", "engine connected")}.get(det_status, ("warn", "engine ?"))
        where = "API (sidecar)" if ss.get("backend_mode") == "sidecar" else "API"
        txt = f"{where} v{health.get('version', '')} · {txt}"
    cols[6].html(f'<div class="status"><span class="dot {dot}"></span>{esc(txt)}</div>')

if health_err:
    with st.container(key="page"):
        section("Backend not available")
        notice("bad", health_err)
        hint("Two-process mode: start the API and reload. Single-command hosts (Streamlit Community Cloud): leave CCT_MODE on "
             "auto (or set it to sidecar); the dashboard then runs `uvicorn backend.main:app` itself, so fastapi, uvicorn and "
             "the backend/ package must be installed next to this app.")
        st.code("uvicorn backend.main:app --port 8000", language="bash")
        st.text_input("API URL", key="api_url")
        if local_backend.bootstrap_log():
            with st.expander("Startup log"):
                st.code("\n".join(local_backend.bootstrap_log()))
    st.stop()


# ============================================================================= secondary pages
def page_runs() -> None:
    with st.container(key="page"):
        section("Runs", "every comparison this server has stored")
        try:
            runs = client().runs()
        except Exception as e:  # noqa: BLE001
            notice("bad", f"Could not list runs: {api_error_text(e)}")
            return
        if not runs:
            hint("No comparison has been run yet.")
            return
        for r in runs[:50]:
            c = st.columns([2.2, 2.4, 1.2, 1.4, 0.9], vertical_alignment="center")
            c[0].html(f'<span class="mono">{esc(r["run_id"][-8:])}</span> <span class="muted">· {esc(local_time(r["created_at"]))}</span>')
            c[1].html(f'{esc(r["release_a"])} → <b>{esc(r["release_b"])}</b>')
            sk = {"completed": "ok", "failed": "bad"}.get(r["status"], "warn")
            c[2].html(chip(sk, r["status"], r.get("error")))
            v = r.get("verdict")
            c[3].html(chip(VERDICT.get(v, ("muted", ""))[0], v) if v else "")
            if c[4].button("Open", key=f"open-{r['run_id']}", width="stretch",
                           type="primary" if r["run_id"] == ss["run_id"] else "secondary"):
                ss["run_id"], ss["page"] = r["run_id"], "Home"
                st.rerun()


def page_engine() -> None:
    with st.container(key="page"):
        left, right = st.columns([1.2, 1], gap="large")
        with left:
            section("Detection engine")
            kind = {"configured": "ok", "auto": "ok", "mock": "warn"}.get(det_status, "bad")
            notice(kind, f"{det_status or 'unknown'} · {det.get('name') or 'no engine loaded'}")
            if det.get("error"):
                hint(det["error"])
            for p in health.get("problems", []):
                notice("warn", p)
            with st.expander("How the API finds the engine"):
                st.markdown("1. `CCT_DETECTOR=\"package.module:function\"` or `\"path/to/engine.py:function\"`\n"
                            "2. auto-discovery of `detection/engine.py` exposing `analyze_releases(release_a, release_b, output_path)`\n"
                            "3. `CCT_DETECTOR=mock` for pipeline testing only\n\n"
                            "Skeleton: `contrib/engine_template.py`.")
        with right:
            section("Server checks")
            qa = qa_status()

            def yes(v):
                return chip("ok", "✓") if v else chip("bad", "✗")
            pid = local_backend.sidecar_pid()
            backend_txt = (f'{esc(ss["api_url"])}<span class="sub">uvicorn sidecar started by the dashboard, pid {pid}</span>'
                           if ss.get("backend_mode") == "sidecar" else f'{esc(ss["api_url"])}<span class="sub">separate process</span>')
            st.html(rows_html([
                ("Backend", backend_txt),
                ("Baseline release (data/tcga-brca/raw)", yes(health.get("baseline_present"))),
                ("Releases discovered", esc(health.get("releases_found"))),
                ("findings.schema.json", yes(health.get("schema_present"))),
                ("validate.py", yes(health.get("validator_present"))),
                ("Quick-fix endpoint", yes(features.get("fixes")) if "fixes" in features else chip("muted", "not advertised")),
                ("Q&A (quick questions)", yes(qa is not None)),
                ("Q&A (typed questions)", chip("ok", "model configured") if qa and qa.get("free_text_available")
                 else chip("muted", "no model (.env)") if qa else chip("muted", "—")),
                ("API version", esc(health.get("version"))),
            ]))
            st.text_input("API URL", key="api_url")


def page_about() -> None:
    with st.container(key="page"):
        section("What this tool is for")
        c1, c2 = st.columns(2, gap="large")
        c1.markdown(
            "**User:** a research engineer responsible for a dataset that gets new releases.\n\n"
            "**Workflow:** pick two releases of the TCGA-BRCA files, see what changed (sample swaps, duplicate profiles, "
            "membership changes, missing measurements), see which reference analyses that affects "
            "(A1: ER-alpha protein by clinical ER status; A2: PAM50 subtype mix of primary tumors), fix what is simple, "
            "send the rest to a researcher, and export `findings.json` (shared format v0.2).")
        c2.markdown(
            "**Judging:** an unseen release with the same five files and no RNA, delivered in a sealed envelope. "
            "The tool must find the changes without being told what to look for.\n\n"
            "**Safety:** de-identified, patient-derived research data. No re-identification, no clinical claims. "
            "Nothing is fixed automatically: every fix is started by a person and can be undone.")


# ============================================================================= home
def page_home() -> None:
    try:
        rels = client().releases()
    except Exception as e:  # noqa: BLE001
        with st.container(key="page"):
            notice("bad", f"Could not list releases: {api_error_text(e)}")
        return
    names = [r["name"] for r in rels]
    by_name = {r["name"]: r for r in rels}

    run_id = ss.get("run_id")
    rec = doc = raw = None
    if run_id:
        try:
            rec = client().run(run_id)
        except Exception as e:  # noqa: BLE001
            st.toast(f"Run {run_id}: {api_error_text(e)}")
            ss["run_id"] = run_id = None
    if rec and rec["status"] == "completed":
        try:
            doc, raw = client().findings(run_id)
        except Exception as e:  # noqa: BLE001
            st.toast(f"Could not load findings: {api_error_text(e)}")

    findings = (doc or {}).get("findings", [])
    analyses = (doc or {}).get("analyses", [])
    repairs = (doc or {}).get("repairs", [])
    decisions = (doc or {}).get("decisions", [])
    summary = (rec or {}).get("summary") or {}
    run_det = (rec or {}).get("detector") or {}

    repairs_by_f: dict[str, list[dict]] = {}
    for r in repairs:
        for fid in r.get("addresses", []):
            repairs_by_f.setdefault(fid, []).append(r)
    decisions_by_r: dict[str, list[dict]] = {}
    for d in decisions:
        decisions_by_r.setdefault(d.get("repair_id"), []).append(d)
    plans = {f["id"]: p for f in findings if (p := fix_plan(f, repairs_by_f.get(f["id"], [])))}
    backend_fixes = bool(doc) and fix_backend_available(run_id, features)
    fixes = load_fixes(run_id, backend_fixes) if doc else []
    fix_index = {(x.get("finding_id"), x.get("record_id")): x for x in fixes}

    ctx = dict(run_id=run_id, rec=rec, doc=doc, raw=raw, findings=findings, analyses=analyses, repairs=repairs,
               decisions=decisions, summary=summary, run_det=run_det, repairs_by_f=repairs_by_f,
               decisions_by_r=decisions_by_r, plans=plans, backend_fixes=backend_fixes, fixes=fixes, fix_index=fix_index)

    main_col, side_col = st.columns([2.4, 1], gap="medium")
    with main_col, st.container(key="main"):
        tabs = st.tabs(["Select release", "Results", "Next steps", "Detailed info", "Assistant"])
        with tabs[0]:
            tab_select(names, by_name, rec)
        with tabs[1]:
            tab_results(ctx)
        with tabs[2]:
            tab_next(ctx)
        with tabs[3]:
            tab_details(ctx, rels)
        with tabs[4]:
            tab_assistant(ctx)
    with side_col, st.container(key="side"):
        running = bool(rec) and rec["status"] in ("pending", "running")
        st.fragment(run_every=1.5 if running else None)(side_panel)(ctx, names)


def not_ready(rec: dict | None, what: str) -> bool:
    """Shared empty state for the result tabs. True when there is nothing to show yet."""
    if not rec:
        hint(f"Compare two releases to see {what} here.")
        return True
    if rec["status"] in ("pending", "running"):
        hint("Comparison running; progress is in the side panel.")
        return True
    if rec["status"] == "failed":
        notice("bad", f"Run failed: {rec.get('error')}")
        errs = (rec.get("validation") or {}).get("errors")
        if errs:
            st.code("\n".join(errs))
        hint("No results are shown for a failed run; nothing was substituted.")
        return True
    return False


# ----------------------------------------------------------------------------- Select release
def tab_select(names: list[str], by_name: dict, rec: dict | None) -> None:
    if not names:
        notice("bad", "No releases found. Run `python data/tcga-brca/fetch.py`, then `make_release.py` or `envelopes/unseal.py`.")
        return
    default_a = names.index("baseline") if "baseline" in names else 0
    others = [i for i, n in enumerate(names) if n != "baseline"]
    picks = []
    cols = st.columns(2, gap="large")
    for col, label, idx in ((cols[0], "Release A · baseline", default_a), (cols[1], "Release B · updated", others[-1] if others else 0)):
        with col:
            name = st.selectbox(label, names, index=idx)
            picks.append(name)
            r = by_name[name]
            rows = []
            for f, present in r["files"].items():
                optional = f not in r["missing_required"] and f.startswith("rna")
                mark = chip("ok", "✓") if present else chip("bad" if not optional else "muted", "—")
                rows.append((f'<span class="{"" if present else "muted"}">{esc(f)}</span>'
                             + (' <span class="muted">(optional)</span>' if optional else ""), mark))
            st.html(rows_html(rows))
            hint(f"{r['origin']} · {r['location']}")
            if r["missing_required"]:
                notice("warn", f"Missing {', '.join(r['missing_required'])}; the engine will see it that way.")
    rel_a, rel_b = picks
    if rel_a == rel_b:
        hint("A and B are the same release: a sanity run that should report nothing.")
    if not engine_ready:
        notice("bad", "No detection engine is connected (see Engine), so Compare is disabled.")
    elif det_status == "mock":
        notice("warn", "The MOCK engine is connected: a run produces placeholder output, not findings.")
    running = bool(rec) and rec["status"] in ("pending", "running")
    c = st.columns([1, 3], vertical_alignment="center")
    if c[0].button("Compare releases", type="primary", disabled=not engine_ready or running, width="stretch"):
        try:
            ss["run_id"] = client().compare(rel_a, rel_b)["run_id"]
            st.rerun()
        except Exception as e:  # noqa: BLE001
            notice("bad", f"Comparison could not start: {api_error_text(e)}")
    with c[1]:
        if running:
            hint("Comparison running; follow it in the side panel.")
        elif rec and rec["status"] == "completed":
            hint(f"Last run {rec['release_a']} → {rec['release_b']} finished; see Results.")
    with st.expander("Add a release (the five files or one .zip)"):
        up_name = st.text_input("Name", placeholder="my-release")
        up_files = st.file_uploader("Files", accept_multiple_files=True, label_visibility="collapsed")
        if st.button("Upload", disabled=not (up_name and up_files)):
            try:
                res = client().upload(up_name, [(f.name, f.getvalue()) for f in up_files])
                st.toast(f"Stored as {res['name']}")
                st.rerun()
            except Exception as e:  # noqa: BLE001
                notice("bad", f"Upload rejected: {api_error_text(e)}")
        hint("Judging day: `python envelopes/unseal.py <n> <code words>` is enough; opened envelopes appear as envelope-<n>.")


# ----------------------------------------------------------------------------- Results
def tab_results(c: dict) -> None:
    if not_ready(c["rec"], "what changed"):
        return
    s, findings = c["summary"], c["findings"]
    if c["run_det"].get("mock"):
        notice("bad", "MOCK run: placeholder output for pipeline testing. Nothing was compared.")
    ra, rb = s.get("release_a", {}), s.get("release_b", {})
    st.html('<div class="stats">'
            + stat("Samples", f"{ra.get('samples', '—')} → {rb.get('samples', '—')}", f"{ra.get('name', 'A')} → {rb.get('name', 'B')}")
            + stat("Patients", f"{ra.get('patients', '—')} → {rb.get('patients', '—')}", "first 12 characters of each id")
            + stat("Ids added / removed", f"+{s.get('samples_added', 0)} / −{s.get('samples_removed', 0)}", "across the whole release")
            + stat("Changed in ≥1 file", s.get("samples_changed_in_any_file", "—"),
                   "same count, different members in a file" if any(d.get("count_equal_membership_differs")
                                                                     for d in (s.get("files") or {}).values()) else "ids added or dropped per file",
                   "warn" if s.get("samples_changed_in_any_file") else "")
            + "</div>")

    # --- analysis impact
    if c["analyses"]:
        section("Analysis impact", "reference analyses rerun only when a change touches what they read")
        acols = st.columns(len(c["analyses"]), gap="medium")
        for col, a in zip(acols, c["analyses"]):
            with col, st.container(key=f"card-an-{a.get('id')}"):
                k, label = analysis_state(a)
                st.html(f'<div class="fhead"><span class="id">{esc(a["id"])}{(" · " + esc(a["title"])) if a.get("title") else ""}</span>'
                        f'{chip(k, label)}</div>'
                        + (f'<div class="fsum">{esc(a["reason"])}</div>' if a.get("reason") else "")
                        + (f'<div class="fmeta">Triggered by {" ".join(chip("muted", t) for t in a["triggered_by"])}</div>'
                           if a.get("triggered_by") else ""))
                before, after = flatten_result(a.get("before") or {}), flatten_result(a.get("after") or {})
                prev = flatten_result(a.get("after_excluding_flagged") or {})
                rows = []
                for key in dict.fromkeys([*before, *after]):
                    x, y = before.get(key, "—"), after.get(key, "—")
                    if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
                        d = round(y - x, 3)
                        delta = chip("muted" if d == 0 else "warn", f"{d:+g}" if d else "0")
                    else:
                        delta = "" if x == y else chip("warn", "changed")
                    extra = f'<span class="sub">excluding flagged: {esc(prev[key])}</span>' if key in prev else ""
                    rows.append((f"{esc(key)}{extra}", f"{esc(x)} → <b>{esc(y)}</b> {delta}"))
                if rows:
                    st.html(rows_html(rows))
                if a.get("before_error"):
                    notice("bad", a["before_error"])
                if a.get("reads"):
                    hint(f"Reads {a['reads']}")
                cmp = a.get("comparison") or {}
                if cmp.get("inputs_added") or cmp.get("inputs_removed"):
                    with st.expander(f"Input samples moved: +{len(cmp.get('inputs_added', []))} / −{len(cmp.get('inputs_removed', []))}"):
                        st.html(rows_html([(f'<span class="mono">{esc(i)}</span>', chip("ok", "added")) for i in cmp.get("inputs_added", [])]
                                          + [(f'<span class="mono">{esc(i)}</span>', chip("bad", "removed")) for i in cmp.get("inputs_removed", [])],
                                          scroll=True))

    # --- findings
    section("Findings", f"{len(findings)} reported by the engine")
    if not findings:
        hint("The engine reported no findings for this pair of releases.")
        return
    rid = c["run_id"]
    fc = st.columns([1.3, 2.4, 1.6, 0.9], vertical_alignment="bottom")
    sev_f = fc[0].pills("Severity", ["high", "medium", "low", "none"], selection_mode="multi", key=f"sev-{rid}")
    kinds = sorted({f.get("kind", "other") for f in findings})
    kind_f = fc[1].pills("Type", kinds, selection_mode="multi", format_func=lambda x: KIND_LABEL.get(x, x), key=f"kind-{rid}")
    q = fc[2].text_input("Search", placeholder="summary, sample id or file", key=f"q-{rid}")
    review_only = fc[3].toggle("Review only", key=f"rev-{rid}")

    def keep(f):
        if sev_f and f.get("severity") not in sev_f:
            return False
        if kind_f and f.get("kind", "other") not in kind_f:
            return False
        if review_only and not f.get("needs_human_review"):
            return False
        hay = " ".join([f.get("summary", ""), f.get("id", ""), finding_file(f), *records_of(f)]).lower()
        return not q or q.lower() in hay

    shown = sorted((f for f in findings if keep(f)), key=lambda f: (SEV_ORDER.get(f.get("severity"), 9), f.get("id", "")))
    if len(shown) != len(findings):
        hint(f"{len(shown)} of {len(findings)} shown.")
    for f in shown:
        finding_card(f, c)


def finding_card(f: dict, c: dict) -> None:
    fid, sev = f["id"], f.get("severity", "none")
    plan = c["plans"].get(fid)
    recs = records_of(f)
    if plan:
        n_done = sum(1 for r in plan["rows"] if (fid, r["id"]) in c["fix_index"])
        fix_chip = chip("ok" if n_done else "accent",
                        (f"{n_done} fixed · " if n_done else "") + ("one-click fix in side panel" if plan["type"] == "exclude" else "fix in Next steps"))
    else:
        fix_chip = chip("muted", "researcher review") if c["repairs_by_f"].get(fid) else ""
    with st.container(key=f"card-f-{fid}"):
        st.html(f'<div class="fhead"><span class="id">{esc(fid)}</span>'
                f'{chip(SEV_KIND.get(sev, "muted"), sev)}{chip("muted", KIND_LABEL.get(f.get("kind"), f.get("kind")))}'
                f'{chip("muted", "confidence " + str(f.get("confidence")))}'
                + "".join(chip("bad", f"affects {a}") for a in f.get("affects_analyses", []))
                + fix_chip + "</div>"
                f'<div class="fsum">{esc(f["summary"])}</div>'
                f'<div class="fmeta">{esc(finding_file(f))}{" · " + str(len(recs)) + " record(s)" if recs else ""}</div>')
        with st.expander("Evidence and reasoning"):
            ev = f.get("evidence", [])
            st.html(rows_html([(f'<span class="mono">{esc(e.get("id"))}</span><span class="sub">{esc(e.get("note", ""))}</span>',
                                chip("muted", e.get("release", e.get("kind")))) for e in ev[:60]], scroll=True))
            if len(ev) > 60:
                hint(f"+{len(ev) - 60} more in findings.json")
            for a, why in (f.get("impact_reasons") or {}).items():
                hint(f"{a}: {why}")
            if f.get("limitation"):
                hint(f"Limitation: {f['limitation']}")
            for r in c["repairs_by_f"].get(fid, []):
                hint(f"Proposed {r['id']} · {ACTION_LABEL.get(r['action'], r['action'])}: {r['justification']}")
            if f.get("details"):
                st.json(f["details"], expanded=False)
            qa = qa_status()
            if qa and qa.get("free_text_available") and st.button(
                    "Ask the assistant about this", key=f"ask-{c['run_id']}-{fid}", type="tertiary"):
                q = f"What does finding {fid} mean, which analyses does it affect, and what repair is proposed?"
                ss["qa_pending"] = {"question": q, "label": q}
                st.toast("Answer is in the Assistant tab")
                st.rerun()


# ----------------------------------------------------------------------------- Next steps
def tab_next(c: dict) -> None:
    if not_ready(c["rec"], "fixes and review items"):
        return
    rid, backend = c["run_id"], c["backend_fixes"]
    if not backend:
        hint("Fix API not connected yet: applied fixes are staged in this browser session only and are not written to findings.json.")

    # --- fixes that need typed input
    relabels = [(f, c["plans"][f["id"]]) for f in c["findings"] if c["plans"].get(f["id"], {}).get("type") == "relabel"]
    section("Fixes that need your input", "type the correct label next to each record")
    if not relabels:
        hint("None for this run.")
    for f, plan in relabels:
        with st.container(key=f"card-rl-{f['id']}"):
            st.html(f'<div class="fhead"><span class="id">{esc(f["id"])}</span>{chip("muted", KIND_LABEL.get(f["kind"]))}'
                    f'{chip(SEV_KIND.get(f.get("severity"), "muted"), f.get("severity"))}</div>'
                    f'<div class="fmeta">{esc(f["summary"])}</div>')
            rows = plan["rows"]
            limit = len(rows) if ss.get(f"all-{rid}-{f['id']}") else 12
            for i, r in enumerate(rows[:limit]):
                relabel_row(rid, backend, f, r, i, c)
            if len(rows) > 12:
                st.toggle(f"Show all {len(rows)} records", key=f"all-{rid}-{f['id']}")

    # --- one-click fixes that did not fit in the side panel
    overflow = [(f, p) for f in c["findings"] if (p := c["plans"].get(f["id"])) and p["type"] == "exclude" and len(p["rows"]) > SIDE_FIX_ROWS]
    if overflow:
        section("More one-click fixes", "the rest of the records the side panel had no room for")
        for f, plan in overflow:
            with st.container(key=f"card-ex-{f['id']}"):
                st.html(f'<div class="fhead"><span class="id">{esc(f["id"])}</span>{chip("muted", KIND_LABEL.get(f["kind"]))}</div>')
                for i, r in enumerate(plan["rows"][SIDE_FIX_ROWS:]):
                    exclude_row(rid, backend, f, r, SIDE_FIX_ROWS + i, c, wide=True)

    # --- everything else goes to a researcher
    review = [r for r in c["repairs"] if not any(c["plans"].get(fid) for fid in r.get("addresses", []))]
    section("For a researcher to decide", "proposals the tool will not apply; the Repair Review Desk records decisions")
    if not review:
        hint("Nothing beyond the fixes above.")
    else:
        for r in review:
            ds = c["decisions_by_r"].get(r["id"], [])
            status = ", ".join(DECISION_LABEL.get(d.get("decision"), str(d.get("decision"))) for d in ds) or "pending"
            with st.container(key=f"card-rv-{r['id']}"):
                st.html(f'<div class="fhead"><span class="id">{esc(r["id"])}</span>'
                        f'{chip("accent", ACTION_LABEL.get(r["action"], r["action"]))}'
                        + "".join(chip("muted", f"resolves {a}") for a in r.get("addresses", []))
                        + chip("muted", f"{len(r.get('targets', []))} target(s)")
                        + chip("ok" if ds else "warn", status) + "</div>"
                        f'<div class="fsum">{esc(r["justification"])}</div>')
                for d in ds:
                    hint(f"{d.get('reviewer_role', 'reviewer')}: {DECISION_LABEL.get(d.get('decision'), d.get('decision'))} — {d.get('reason', '')}")

    # --- log + export
    section("Applied fixes", "staged in this session" if not backend else "recorded by the backend")
    if not c["fixes"]:
        hint("No fixes applied yet.")
    else:
        rows = []
        for x in c["fixes"]:
            what = "removed" if x.get("action") == "exclude" else f"{x.get('field', 'label')} → “{x.get('new_value', '')}”"
            rows.append((f'<span class="mono">{esc(x.get("record_id"))}</span> <span class="muted">{esc(x.get("finding_id"))} · {esc(what)}</span>',
                         chip("ok" if x.get("status") == "applied" else "warn", x.get("status", "staged"))))
        st.html(rows_html(rows, scroll=True))

    section("Export")
    st.download_button("Download findings.json", data=c["raw"], file_name=f"findings-{rid}.json", mime="application/json",
                       type="primary", key="dl", on_click=lambda: ss["exported"].add(rid))
    hint(f"The exact file the backend validated. Re-check with: python format/validate.py findings-{rid}.json")


def relabel_row(rid: str, backend: bool, f: dict, r: dict, i: int, c: dict) -> None:
    done = c["fix_index"].get((f["id"], r["id"]))
    cols = st.columns([2.2, 1.7, 2.3, 0.9], vertical_alignment="center")
    values = ""
    if r.get("value_a") is not None or r.get("value_b") is not None:
        values = f'<span class="sub">A: {esc(r.get("value_a", "?"))} → B: {esc(r.get("value_b", "?"))}</span>'
    cols[0].html(f'<div class="fixrow"><span class="mono{" done-txt" if done else ""}">{esc(r["id"])}</span>{values}</div>')
    fields = r["fields"] or ["(field)"]
    if done:
        cols[1].html(f'<div class="fixrow">{esc(done.get("field"))}</div>')
        cols[2].html(f'<div class="fixrow">{chip("ok", "set to “" + str(done.get("new_value")) + "”")}</div>')
        if cols[3].button("Undo", key=f"undo-rl-{rid}-{f['id']}-{i}", width="stretch"):
            undo_fix(rid, backend, done["fix_id"])
        return
    if len(fields) > 1:
        field = cols[1].selectbox("Field", fields, key=f"fld-{rid}-{f['id']}-{i}", label_visibility="collapsed")
    else:
        field = fields[0]
        cols[1].html(f'<div class="fixrow" title="{esc(field)}">{esc(field if len(field) < 34 else field[:32] + "…")}</div>')
    ph = f"New label (A was {r['value_a']})" if r.get("value_a") is not None else "New label"
    new = cols[2].text_input("New label", key=f"lbl-{rid}-{f['id']}-{i}", placeholder=ph, label_visibility="collapsed")
    if cols[3].button("Apply", key=f"apply-rl-{rid}-{f['id']}-{i}", type="primary", disabled=not new.strip(), width="stretch"):
        apply_fix(rid, backend, {"finding_id": f["id"], "repair_id": next((x["id"] for x in c["repairs_by_f"].get(f["id"], [])), None),
                                 "action": "relabel", "record_id": r["id"], "file": r["file"], "field": field,
                                 "new_value": new.strip()})


def exclude_row(rid: str, backend: bool, f: dict, r: dict, i: int, c: dict, wide: bool = False) -> None:
    done = c["fix_index"].get((f["id"], r["id"]))
    cols = st.columns([3, 1.4] if not wide else [5, 1], vertical_alignment="center")
    note = r["note"].split(";")[0].split(": ", 1)[-1] if r.get("note") else ""
    tag = ' <span class="chip accent">suggested</span>' if r.get("suggested") and not done else ""
    cols[0].html(f'<div class="fixrow"><span class="mono{" done-txt" if done else ""}">{esc(r["id"])}</span>{tag}'
                 f'<span class="sub">{esc(note)}</span></div>')
    side = "side" if not wide else "wide"
    if done:
        if cols[1].button("Undo", key=f"undo-ex-{side}-{rid}-{f['id']}-{i}", width="stretch"):
            undo_fix(rid, backend, done["fix_id"])
    elif cols[1].button("Remove", key=f"apply-ex-{side}-{rid}-{f['id']}-{i}", width="stretch"):
        apply_fix(rid, backend, {"finding_id": f["id"], "repair_id": next((x["id"] for x in c["repairs_by_f"].get(f["id"], [])), None),
                                 "action": "exclude", "record_id": r["id"], "file": r["file"]})


# ----------------------------------------------------------------------------- Detailed info
def tab_details(c: dict, rels: list[dict]) -> None:
    if not_ready(c["rec"], "provenance"):
        section("Releases on this server")
        st.html(rows_html([(f'{esc(r["name"])}<span class="sub">{esc(r["origin"])} · {esc(r["location"])}</span>',
                            chip("ok", "complete") if not r["missing_required"] else chip("warn", "missing " + ", ".join(r["missing_required"])))
                           for r in rels]))
        return
    rec, doc, s = c["rec"], c["doc"], c["summary"]
    left, right = st.columns([1, 1.15], gap="large")
    with left:
        section("Run")
        v = rec.get("validation") or {}
        st.html(rows_html([
            ("Run id", f'<span class="mono">{esc(rec["run_id"])}</span>'),
            ("Releases", f'{esc(rec["release_a"])} → {esc(rec["release_b"])}'),
            ("Engine", f'<span title="{esc(c["run_det"].get("name"))}">{esc(short_engine(c["run_det"].get("name")))}</span> '
                       f'<span class="muted">({esc(c["run_det"].get("source"))})</span>'),
            ("Started → finished", f'{esc(local_time(rec.get("started_at") or rec["created_at"]))} → {esc(local_time(rec.get("finished_at")))}'),
            ("Validator", chip("ok" if v.get("valid") else "bad", ("passed " if v.get("valid") else "failed ") + str(v.get("validator", "")))),
        ]))
        if doc.get("question"):
            hint(f"Question: {doc['question']}")
    with right:
        section("Files", "sample ids from each file's header; hashes for provenance")
        hashes: dict[str, dict[str, str]] = {}
        for i, r in enumerate((doc.get("data") or {}).get("releases", [])):
            for fl in r.get("files", []):
                hashes.setdefault(fl.get("file") or fl.get("name"), {})["AB"[min(i, 1)]] = fl.get("sha256")
        rows = []
        for fname, d in (s.get("files") or {}).items():
            a, b = d.get("samples_a"), d.get("samples_b")
            counts = f"{a if a is not None else '—'} → {b if b is not None else 'absent'}"
            tags = ""
            if d.get("added") or d.get("removed"):
                tags += chip("warn", f"+{d.get('added', 0)} / −{d.get('removed', 0)}")
            if d.get("count_equal_membership_differs"):
                tags += chip("bad", "same count, different members")
            h = hashes.get(fname, {})
            hs = " · ".join(f'{k} <span class="mono" title="{esc(v)}">{esc(short_hash(v))}</span>' for k, v in h.items() if v)
            rows.append((f'{esc(fname)}<span class="sub">{hs}{(" · " + esc(d["error"])) if d.get("error") else ""}</span>',
                         f"{tags} {esc(counts)}"))
        st.html(rows_html(rows))
        hint("Baseline hashes are of the downloaded file; other releases hash the decompressed content of .gz files, "
             "so .gz hashes are not comparable across A and B.")
    with st.expander("Progress log"):
        st.code("\n".join(rec.get("progress") or []) or "(empty)")
    with st.expander("findings.json"):
        st.json(doc, expanded=False)
    if (doc.get("producer") or {}).get("engine_producer") or (doc.get("data") or {}).get("engine_data"):
        with st.expander("Engine-reported metadata"):
            st.json({"producer": doc["producer"].get("engine_producer"), "data": doc["data"].get("engine_data")}, expanded=False)
    for n in s.get("notes", []):
        hint(n)


# ----------------------------------------------------------------------------- Assistant
SOURCE_LABEL = {  # how /ask produced the answer (detection/qa.py)
    "deterministic": ("ok", "from findings.json"),
    "llm": ("accent", "model answer · citations checked"),
    "refusal": ("muted", "declined"),
    "rejected": ("warn", "model answer rejected"),
    "unavailable": ("warn", "model unavailable"),
}


@st.cache_data(ttl=30, show_spinner=False)
def fetch_qa_chips(url: str) -> dict | None:
    return ApiClient(url).qa_chips()


def qa_status() -> dict | None:
    """{"chips": [...], "free_text_available": bool}, or None when this backend has no Q&A endpoints."""
    try:
        return fetch_qa_chips(ss["api_url"])
    except Exception:  # noqa: BLE001
        return None


def tab_assistant(c: dict) -> None:
    rid = c["run_id"]
    if not c["doc"]:
        hint("Ask questions about a run once a comparison has finished.")
        return
    qa = qa_status()
    if qa is None:
        notice("muted", "Q&A is not available on this backend (no /api/qa/chips or /api/runs/{id}/ask).")
        return
    free = bool(qa.get("free_text_available"))
    hist = ss.setdefault("qa_hist", {}).setdefault(rid, [])
    titles = {f["id"]: f.get("summary", "") for f in c["findings"]} | {r["id"]: r.get("justification", "") for r in c["repairs"]}

    top = st.columns([5, 1], vertical_alignment="center")
    top[0].html(f'<div class="hint">Answers come only from this run\'s findings.json '
                f'(<span class="mono">{esc(rid[-8:])}</span>, {esc(c["rec"]["release_a"])} → {esc(c["rec"]["release_b"])}). '
                "Every id an answer mentions is checked against it. Each question is answered on its own.</div>")
    if hist and top[1].button("Clear", type="tertiary", key=f"qa-clear-{rid}"):
        hist.clear()
        st.rerun()

    # preset questions: answered by plain code, always available
    chips = qa.get("chips", [])
    picked = st.pills("Quick questions", [x["id"] for x in chips], format_func=lambda i: next(x["label"] for x in chips if x["id"] == i),
                      key=f"qa-chip-{rid}-{len(hist)}")
    if picked:
        ss["qa_pending"] = {"chip": picked, "label": next(x["label"] for x in chips if x["id"] == picked)}

    box = st.container(height=430, border=False)
    with box:
        if not hist:
            hint("Pick a quick question above" + (", or type your own below." if free else ". Free-text questions need a model (see below)."))
        for m in hist:
            with st.chat_message(m["role"]):
                if m["role"] == "user":
                    st.markdown(esc(m["content"]))
                    continue
                kind, label = SOURCE_LABEL.get(m.get("source"), ("muted", m.get("source") or ""))
                st.html(f'<div style="white-space:pre-wrap;line-height:1.5">{esc(m["content"])}</div>'
                        + (f'<div style="margin-top:.4rem">{"".join(chip("muted", x, titles.get(x)) for x in m.get("citations", [])[:24])}'
                           + (f'<span class="muted"> +{len(m["citations"]) - 24} more</span>' if len(m.get("citations", [])) > 24 else "")
                           + "</div>" if m.get("citations") else "")
                        + f'<div style="margin-top:.3rem">{chip(kind, label)}'
                        + (f'<span class="muted" style="font-size:.78rem">{esc(m["reason"])}</span>' if m.get("reason") else "") + "</div>")

    typed = st.chat_input("Ask about this run" if free else "Free-text questions need a model", key=f"qa-in-{rid}", disabled=not free)
    if not free:
        hint("To enable typed questions, set LLM_BASE_URL and OPENAI_MODEL (local Ollama) or OPENAI_API_KEY in the repo's .env "
             "and restart the API. The quick questions work without a model.")
    pending = {"question": typed, "label": typed} if typed else ss.pop("qa_pending", None)
    if pending and pending.get("question") and not free:
        pending = None
    if pending:
        hist.append({"role": "user", "content": pending["label"]})
        with box, st.spinner("Answering…" if pending.get("chip") else "Asking the model… (a local model can take a while)"):
            try:
                res = client().ask(rid, question=pending.get("question") or "", chip=pending.get("chip"))
            except Exception as e:  # noqa: BLE001
                res = {"answer": f"The request failed: {api_error_text(e)}", "citations": [], "source": "unavailable"}
        if res is None:
            res = {"answer": "This backend has no /ask endpoint.", "citations": [], "source": "unavailable"}
        hist.append({"role": "assistant", "content": res.get("answer", ""), "citations": res.get("citations", []),
                     "source": res.get("source"), "reason": res.get("reason")})
        st.rerun()


# ----------------------------------------------------------------------------- side panel
def side_panel(c: dict, names: list[str]) -> None:
    rec, doc = c["rec"], c["doc"]
    if rec and rec["status"] in ("pending", "running"):
        try:
            rec = client().run(rec["run_id"])
        except Exception:  # noqa: BLE001
            pass
        if rec["status"] in ("completed", "failed"):
            st.rerun()

    section("Quick summary")
    if doc:
        verdict = doc.get("verdict")
        vk, vt = VERDICT.get(verdict, ("muted", "No verdict from the engine."))
        sev = (c["summary"].get("metrics") or {}).get("by_severity") or {}
        review_n = sum(1 for f in c["findings"] if f.get("needs_human_review"))
        one_click = sum(len(p["rows"]) for p in c["plans"].values() if p["type"] == "exclude")
        typed = sum(len(p["rows"]) for p in c["plans"].values() if p["type"] == "relabel")
        st.html('<div class="stats two">'
                + stat("Verdict", verdict or "—", vt, vk)
                + stat("Findings", len(c["findings"]), " · ".join(f"{k} {v}" for k, v in sev.items()) or "none",
                       "bad" if sev.get("high") else "")
                + stat("Needs a researcher", review_n, f"{len(c['repairs'])} proposed repair(s)", "warn" if review_n else "ok")
                + stat("Fixes applied", len(c["fixes"]), f"{one_click} one-click · {typed} need input")
                + "</div>")
        if c["run_det"].get("mock"):
            notice("bad", "MOCK engine: placeholder output.")
    elif rec:
        hint(f"{rec['release_a']} → {rec['release_b']} · {rec['status']}")
    else:
        st.html('<div class="stats two">'
                + stat("Engine", {"mock": "MOCK", "auto": "ready", "configured": "ready"}.get(det_status, "missing"),
                       short_engine(det.get("name")), "ok" if engine_ready and det_status != "mock" else "warn")
                + stat("Releases", len(names), ", ".join(names[:3]) + (" …" if len(names) > 3 else ""),
                       "ok" if "baseline" in names else "bad")
                + "</div>")

    section("Workflow")
    status = (rec or {}).get("status")
    last = (rec or {}).get("progress") or []
    last_msg = last[-1].split(" ", 1)[-1] if last else "queued"
    valid = bool(((rec or {}).get("validation") or {}).get("valid"))
    n_fix_rows = sum(len(p["rows"]) for p in c["plans"].values())
    steps = [
        ("done" if len(names) >= 2 else "todo", "Releases available", f"{len(names)} on this server"),
        ("done" if engine_ready and det_status != "mock" else "fail" if not engine_ready else "active",
         "Detection engine connected", short_engine(det.get("name"))),
        ({"completed": "done", "failed": "fail", "running": "active", "pending": "active"}.get(status, "todo"),
         "Compare releases", last_msg if status in ("running", "pending") else (rec or {}).get("error") or ""),
        ("done" if valid else "fail" if status == "failed" else "todo", "findings.json validated", ""),
        ("done" if doc and (c["decisions"] or (n_fix_rows and len(c["fixes"]) >= n_fix_rows)) else "active" if doc else "todo",
         "Fix and review", f"{len(c['fixes'])} of {n_fix_rows} quick fixes applied" if doc else ""),
        ("done" if c["run_id"] in ss["exported"] else "active" if doc else "todo", "Export findings.json", ""),
    ]
    icon = {"done": "✓", "fail": "✕", "active": "•", "todo": ""}
    st.html('<div class="steps">' + "".join(
        f'<div class="step {k}"><span class="i">{icon[k] or n}</span><span class="t">{esc(t)}'
        + (f"<small>{esc(sub)}</small>" if sub else "") + "</span></div>"
        for n, (k, t, sub) in enumerate(steps, 1)) + "</div>")

    if not doc:
        return
    section("One-click fixes")
    ex = [(f, p) for f in c["findings"] if (p := c["plans"].get(f["id"])) and p["type"] == "exclude"]
    if not ex:
        hint("No one-click fixes for this run.")
        return
    if not c["backend_fixes"]:
        hint("Staged in this session until the fix API is connected.")
    for f, plan in ex:
        st.html(f'<div class="fhead" style="margin-top:.4rem"><span class="id">{esc(f["id"])}</span>'
                f'{chip("muted", KIND_LABEL.get(f["kind"]))}</div>')
        for i, r in enumerate(plan["rows"][:SIDE_FIX_ROWS]):
            exclude_row(c["run_id"], c["backend_fixes"], f, r, i, c)
        if len(plan["rows"]) > SIDE_FIX_ROWS:
            hint(f"+{len(plan['rows']) - SIDE_FIX_ROWS} more in Next steps")


# ============================================================================= route
{"Runs": page_runs, "Engine": page_engine, "About": page_about}.get(ss["page"], page_home)()
st.html('<div class="footer">Research use only · de-identified, patient-derived data · no clinical claims · '
        'every fix is started by a person</div>')
