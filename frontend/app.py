"""Cohort Control Tower — Streamlit dashboard (v4).

Run (from the repository root, with the API already running):
    streamlit run frontend/app.py

Layout: full-width page. A top bar (project name, Home | Runs | Engine | Mission, Dark/Light switch,
API/engine status). On Home, the work panel (Select release | Results | Next steps | Detailed info) sits
left and the quick-summary panel (face cards + automatic-fix candidates) sits right; inside the tabs,
content is laid out in columns before it stacks. No sidebar.

All data comes from the FastAPI backend over HTTP; the dashboard computes no findings itself.
Tables are rendered as HTML so they take the panel's colours in both themes.
Works with the Busy Beavers backend as is: when GET /api/runs/{id}/triage is absent, the quick-summary
panel falls back to what findings.json itself says and marks the risk tier / automatic-fix list as unavailable.
"""
from __future__ import annotations

import html
import os
import sys
import time

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_client import DEFAULT_URL, ApiClient, ApiError  # noqa: E402

st.set_page_config(page_title="Cohort Control Tower", page_icon="🛰️", layout="wide",
                   initial_sidebar_state="collapsed")

# ----------------------------------------------------------------------------- themes
THEMES = {
    "dark": dict(page="#171311", bar="#241c18", bar_text="#f1e8dd", bar_muted="#b39d88",
                 panel1="#221b17", panel2="#2a2220", sub="#2d2521", line="#4a3d35", ink="#efe6dc", muted="#b8a797",
                 accent="#c9823b", ok="#7fb77e", warn="#e0a458", bad="#e0735b",
                 table_head="#2f2621", table_row="rgba(255,255,255,.025)", table_alt="rgba(255,255,255,.055)",
                 input_bg="#2f2622", input_text="#f1e8dd", card="#2a2220", flag_bad="#4a2a24", flag_ok="#2d4a2f",
                 flag_warn="#4d3b1f", flag_muted="#3a322d", btn_primary="#c9823b", btn_primary_text="#1a120c"),
    "light": dict(page="#e4ddd3", bar="#3f322a", bar_text="#f4ede4", bar_muted="#c7b6a4",
                  panel1="#efe9e1", panel2="#e9e1d7", sub="#f3eee7", line="#c4b7a8", ink="#2a221c", muted="#6d6057",
                  accent="#9a5b22", ok="#3f7a46", warn="#9a6a1f", bad="#9a3a2a",
                  table_head="#e3dacf", table_row="rgba(0,0,0,.015)", table_alt="rgba(0,0,0,.045)",
                  input_bg="#f7f3ee", input_text="#2a221c", card="#f5f0e9", flag_bad="#f0dcd6", flag_ok="#dcebdc",
                  flag_warn="#f3e5c9", flag_muted="#e4dcd2", btn_primary="#9a5b22", btn_primary_text="#fff8f0"),
}

CSS = """
<style>
:root {{ {vars} }}
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {{ background: var(--page) !important; color: var(--ink); }}
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{ display: none; }}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],
section[data-testid="stSidebar"] {{ display: none !important; }}
.block-container {{ padding: 0.8rem 1.6rem 2rem 1.6rem; max-width: 100% !important; }}
h1, h2, h3, h4, h5, p, li, span, label, .stMarkdown {{ color: var(--ink); }}
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label, label[data-testid="stWidgetLabel"],
[data-testid="stCaptionContainer"] {{ color: var(--ink) !important; opacity: 1 !important; font-weight: 600; font-size: .95rem; }}
code {{ color: var(--accent); background: var(--sub); }}

/* inputs follow the theme */
[data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="base-input"], textarea, input {{
  background: var(--input-bg) !important; color: var(--input-text) !important; border-color: var(--line) !important; }}
[data-baseweb="select"] span, [data-baseweb="select"] div, [data-baseweb="select"] input {{ color: var(--input-text) !important; }}
[data-baseweb="select"] svg {{ fill: var(--input-text) !important; }}
ul[data-baseweb="menu"], ul[data-baseweb="menu"] li {{ background: var(--input-bg) !important; color: var(--input-text) !important; }}
[data-testid="stExpander"] details, [data-testid="stExpander"] summary {{ background: var(--sub); border-color: var(--line) !important; color: var(--ink) !important; }}
[data-testid="stExpander"] summary p, [data-testid="stExpander"] summary span {{ color: var(--ink) !important; }}
[data-testid="stFileUploaderDropzone"] {{ background: var(--sub) !important; border-color: var(--line) !important; color: var(--ink) !important; }}
[data-testid="stFileUploaderDropzone"] * {{ color: var(--ink) !important; }}
[data-testid="stCheckbox"] p {{ color: var(--ink) !important; }}
.stButton > button, .stDownloadButton > button {{
  background: var(--sub); color: var(--ink); border: 1px solid var(--line); border-radius: 6px; font-weight: 600; }}
.stButton > button:hover, .stDownloadButton > button:hover {{ border-color: var(--accent); color: var(--accent); }}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {{
  background: var(--btn-primary); color: var(--btn-primary-text); border-color: var(--btn-primary); }}
.stButton > button *, .stDownloadButton > button * {{ color: inherit !important; }}
.stButton > button[kind="primary"] *, .stDownloadButton > button[kind="primary"] * {{ color: var(--btn-primary-text) !important; }}
.stButton > button:disabled {{ opacity: .45; }}
[data-testid="stMetric"] {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: .6rem .9rem; }}
[data-testid="stMetricLabel"] p, [data-testid="stMetricValue"], [data-testid="stMetricDelta"] {{ color: var(--ink) !important; }}
[data-testid="stJson"] {{ background: var(--sub); border-radius: 6px; padding: .4rem; }}
pre, [data-testid="stCode"] pre {{ background: var(--sub) !important; color: var(--ink) !important; }}
hr {{ border-color: var(--line); }}

/* top bar */
.st-key-topbar {{ background: var(--bar); border-radius: 10px; padding: .7rem 1.4rem; margin-bottom: 1rem; }}
.st-key-topbar .cct-brand {{ color: var(--bar-text); font-size: 1.55rem; font-weight: 700; letter-spacing: .02em; line-height: 2.6rem; white-space: nowrap; }}
.st-key-topbar .cct-brand small {{ color: var(--bar-muted); font-weight: 400; font-size: .85rem; margin-left: .7rem; }}
.st-key-topbar .stButton, .st-key-topbar [data-testid="stButton"] {{ width: 100%; }}
.st-key-topbar .stButton > button {{ background: transparent; color: var(--bar-text); border: 1px solid transparent;
  border-radius: 8px; width: 100%; min-height: 2.7rem; font-weight: 700; font-size: 1.08rem; padding: .5rem 1.4rem; }}
.st-key-topbar .stButton > button * {{ color: var(--bar-text) !important; font-size: 1.08rem !important; }}
.st-key-topbar .stButton > button:hover {{ border-color: var(--bar-muted); }}
.st-key-topbar .stButton > button[kind="primary"] {{ background: var(--accent); border-color: var(--accent); }}
.st-key-topbar .stButton > button[kind="primary"] * {{ color: var(--btn-primary-text) !important; }}
.st-key-topbar .cct-status {{ color: var(--bar-muted); font-size: .9rem; text-align: right; line-height: 2.6rem; white-space: nowrap; }}

/* panels: the two home columns stretch to the same height */
[data-testid="stHorizontalBlock"] {{ align-items: stretch; }}
[data-testid="stColumn"] > div, [data-testid="stColumn"] > div > div {{ height: 100%; }}
.st-key-panel2 {{ height: 100%; }}
.st-key-panel1, .st-key-panel2 {{ border-radius: 12px; box-sizing: border-box; padding: 1rem 1.4rem 1.3rem; border: 1px solid var(--line); }}
.st-key-panel1 {{ background: var(--panel1); }}
.st-key-panel2 {{ background: var(--panel2); }}
[class*="st-key-subpanel"] {{ background: var(--sub); border: 1px solid var(--line); border-radius: 8px; padding: .8rem 1rem; }}

/* tabs: large, centred, readable */
[data-testid="stTabs"] div[role="tablist"], [data-testid="stTabs"] [data-baseweb="tab-list"] {{
  justify-content: center !important; gap: .8rem; border-bottom: 2px solid var(--line); background: transparent; padding-bottom: 0; }}
[data-testid="stTabs"] button[role="tab"], [data-testid="stTabs"] [data-baseweb="tab"] {{
  flex: 0 1 auto; min-width: 11rem; padding: .85rem 2rem !important; border-radius: 10px 10px 0 0; background: transparent;
  height: auto !important; justify-content: center; }}
[data-testid="stTabs"] button[role="tab"] *, [data-testid="stTabs"] [data-baseweb="tab"] * {{
  color: var(--ink) !important; font-size: 1.2rem !important; line-height: 1.5rem !important; font-weight: 700 !important; opacity: 1 !important; }}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"], [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {{ background: var(--sub); }}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] *, [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] * {{ color: var(--accent) !important; }}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ background: var(--accent); height: 4px; }}
[data-testid="stTabs"] [data-baseweb="tab-border"] {{ background: transparent; }}
[data-testid="stTabs"] [data-baseweb="tab-panel"] {{ padding-top: 1rem; }}

/* HTML tables inset into the panel */
.cct-tablewrap {{ overflow: auto; border: 1px solid var(--line); border-radius: 6px; box-shadow: inset 0 1px 4px rgba(0,0,0,.18); margin: .3rem 0 .6rem; }}
.cct-tablewrap table {{ width: 100%; border-collapse: collapse; font-size: .92rem; color: var(--ink); }}
.cct-tablewrap th {{ position: sticky; top: 0; background: var(--table-head); color: var(--ink); text-align: left; padding: .5rem .7rem;
  font-weight: 700; border-bottom: 1px solid var(--line); white-space: nowrap; }}
.cct-tablewrap td {{ padding: .42rem .7rem; border-bottom: 1px solid var(--line); vertical-align: top; background: var(--table-row); }}
.cct-tablewrap tr:nth-child(even) td {{ background: var(--table-alt); }}
.cct-tablewrap td.num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.cct-tablewrap td.sev-high {{ color: var(--bad); font-weight: 700; }}
.cct-tablewrap td.sev-medium {{ color: var(--warn); font-weight: 700; }}

/* notices, cards, flags */
.cct-note {{ border-left: 3px solid var(--line); padding: .4rem .9rem; margin: .35rem 0; color: var(--ink);
             background: var(--sub); border-radius: 0 6px 6px 0; font-size: .95rem; }}
.cct-note.ok {{ border-left-color: var(--ok); }}  .cct-note.warn {{ border-left-color: var(--warn); }}
.cct-note.bad {{ border-left-color: var(--bad); }} .cct-note.muted {{ color: var(--muted); }}
.cct-card {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: .8rem 1rem; min-height: 6.2rem; margin-bottom: .6rem; }}
.cct-card .k {{ color: var(--muted); font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; }}
.cct-card .v {{ font-size: 1.6rem; font-weight: 700; color: var(--ink); margin: .15rem 0; }}
.cct-card .s {{ color: var(--muted); font-size: .85rem; }}
.cct-flag {{ display: inline-block; border-radius: 4px; padding: .1rem .55rem; font-size: .8rem; font-weight: 700; margin-right: .3rem; }}
.cct-flag.bad {{ background: var(--flag-bad); color: var(--bad); }}  .cct-flag.ok {{ background: var(--flag-ok); color: var(--ok); }}
.cct-flag.warn {{ background: var(--flag-warn); color: var(--warn); }} .cct-flag.muted {{ background: var(--flag-muted); color: var(--muted); }}
.cct-kv {{ color: var(--muted); font-size: .88rem; }}
.cct-h {{ font-size: 1.15rem; font-weight: 700; color: var(--ink); margin: .4rem 0 .3rem; }}
</style>
"""

VERDICT_TEXT = {
    "Ready": ("ok", "No material change detected."),
    "Conditional": ("warn", "Usable after the flagged items are reviewed."),
    "Blocked": ("bad", "Material changes affect a protected analysis; review before use."),
    "Insufficient Evidence": ("warn", "The engine could not check enough to support a decision."),
}
KIND_LABEL = {"sample_swap": "Sample swap", "duplicate": "Duplicate profile", "missing_data": "Missing data / coverage",
              "membership_change": "Membership change", "label_conflict": "Label conflict", "join_inflation": "Join inflation",
              "unlinked_record": "Unlinked record", "claim_check": "Claim check", "other": "Other change"}
SEV_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3}
RECORD_KINDS = ("sample", "patient", "row")


# ----------------------------------------------------------------------------- helpers
def client() -> ApiClient:
    return ApiClient(st.session_state.get("api_url", DEFAULT_URL))


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def note(kind: str, text: str) -> None:
    st.html(f'<div class="cct-note {kind}">{esc(text)}</div>')


def flag(kind: str, text: str) -> str:
    return f'<span class="cct-flag {kind}">{esc(text)}</span>'


def heading(text: str) -> None:
    st.html(f'<div class="cct-h">{esc(text)}</div>')


def kv(text: str) -> None:
    st.html(f'<div class="cct-kv">{esc(text)}</div>')


def card(label: str, value, sub: str = "", flag_html: str = "") -> None:
    st.html(f'<div class="cct-card"><div class="k">{esc(label)}</div><div class="v">{esc(value)}</div>'
            f'<div class="s">{flag_html}{esc(sub)}</div></div>')


def table(rows: list[dict] | pd.DataFrame, max_height: int = 420, index_name: str | None = None) -> None:
    """Theme-matched HTML table (replaces st.dataframe so colours follow the panel)."""
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if df.empty:
        note("muted", "(empty)")
        return
    if index_name is not None:
        df = df.reset_index().rename(columns={"index": index_name})
    head = "".join(f"<th>{esc(c)}</th>" for c in df.columns)
    body = []
    for _, r in df.iterrows():
        cells = []
        for c in df.columns:
            v = r[c]
            cls = []
            if isinstance(v, (int, float)) and not isinstance(v, bool) and not pd.isna(v):
                cls.append("num")
            if c == "severity" and v in ("high", "medium"):
                cls.append(f"sev-{v}")
            txt = "" if v is None or (isinstance(v, float) and pd.isna(v)) else v
            if isinstance(txt, float) and txt.is_integer():
                txt = int(txt)
            cells.append(f'<td class="{" ".join(cls)}">{esc(txt)}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    st.html(f'<div class="cct-tablewrap" style="max-height:{max_height}px"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def api_error_text(e: Exception) -> str:
    if isinstance(e, ApiError):
        return f"{e.message}" + (f" (HTTP {e.status})" if e.status else "")
    return f"{type(e).__name__}: {e}"


def ev_rows(evidence: list[dict]) -> list[dict]:
    rows = [{"kind": e.get("kind"), "id": e.get("id"), "release": e.get("release", ""),
             "file": e.get("file", ""), "note": e.get("note", ""), "url": e.get("url", "")} for e in evidence]
    if not any(r["url"] for r in rows):
        for r in rows:
            r.pop("url")
    return rows


def records_of(f: dict) -> list[str]:
    return list(dict.fromkeys(e["id"] for e in f.get("evidence", []) if e.get("kind") in RECORD_KINDS))


def finding_files(f: dict) -> str:
    """The finding's file; engines that don't set `file` name it in each evidence pointer instead."""
    if f.get("file"):
        return f["file"]
    return ", ".join(dict.fromkeys(e["file"] for e in f.get("evidence", []) if e.get("file")))


DECISION_LABEL = {"approve": "approve", "reject": "reject", "request_more_evidence": "more evidence requested"}


def flatten_result(d: dict) -> dict:
    """Analysis result -> {row label: value}; nested dicts become one row per key, lists are joined."""
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


def before_after_rows(a: dict) -> list[dict]:
    cols = [(t, flatten_result(d)) for t, d in (("Before (A)", a.get("before")), ("After (B)", a.get("after")),
                                                ("After excluding flagged (preview)", a.get("after_excluding_flagged"))) if d]
    keys = list(dict.fromkeys(k for _, d in cols for k in d if k != "inputs"))
    rows = []
    for k in keys:
        row = {"result": k, **{t: d.get(k, "—") for t, d in cols}}
        if "Before (A)" in row and "After (B)" in row:
            x, y = row["Before (A)"], row["After (B)"]
            if x == "—" or y == "—":
                row["Δ (B − A)"] = "only in B" if x == "—" else "only in A"
            elif isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
                row["Δ (B − A)"] = f"{round(y - x, 3):+g}" if y != x else "0"
            else:
                row["Δ (B − A)"] = "" if x == y else "changed"
        rows.append(row)
    return rows


@st.cache_data(ttl=5, show_spinner=False)
def fetch_health(url: str) -> dict:
    return ApiClient(url).health()


# ----------------------------------------------------------------------------- state & theme
st.session_state.setdefault("api_url", os.environ.get("CCT_API_URL", DEFAULT_URL))
st.session_state.setdefault("page", "Home")
st.session_state.setdefault("run_id", None)
if "theme" not in st.session_state:
    base = "dark"
    try:
        base = st.context.theme.type or "dark"
    except Exception:  # noqa: BLE001
        pass
    st.session_state["theme"] = base if base in THEMES else "dark"
T = THEMES[st.session_state["theme"]]
st.html(CSS.format(vars=" ".join(f"--{k.replace('_', '-')}: {v};" for k, v in T.items())))

health, health_err = None, None
try:
    health = fetch_health(st.session_state["api_url"])
except Exception as e:  # noqa: BLE001
    health_err = api_error_text(e)
det = (health or {}).get("detector", {}) or {}
det_status = det.get("status")
engine_ready = det_status in ("configured", "auto", "mock")

# ----------------------------------------------------------------------------- top bar
with st.container(key="topbar"):
    cols = st.columns([3, 1.1, 1.1, 1.1, 1.1, 0.9, 2.4], vertical_alignment="center")
    cols[0].html('<div class="cct-brand">Cohort Control Tower<small>TCGA-BRCA · Cohort Firewall</small></div>')
    for col, name in zip(cols[1:5], ("Home", "Runs", "Engine", "Mission")):
        if col.button(name, key=f"nav-{name}", width="stretch", type="primary" if st.session_state["page"] == name else "secondary"):
            st.session_state["page"] = name
            st.rerun()
    other = "light" if st.session_state["theme"] == "dark" else "dark"
    if cols[5].button(("☀ Light" if other == "light" else "☾ Dark"), key="theme-toggle", width="stretch"):
        st.session_state["theme"] = other
        st.rerun()
    if health_err:
        status_txt = "API offline"
    else:
        status_txt = {"mock": "engine: MOCK", "not_configured": "engine: not configured", "error": "engine: load error",
                      "auto": "engine: auto-discovered", "configured": "engine: connected"}.get(det_status, "engine: ?")
        status_txt = f"API v{health.get('version', '')} · {status_txt}"
    cols[6].html(f'<div class="cct-status">{esc(status_txt)}</div>')

page = st.session_state["page"]

if health_err:
    with st.container(key="panel1"):
        heading("API not reachable")
        note("bad", health_err)
        st.code("uvicorn backend.main:app --port 8000", language="bash")
        st.text_input("API URL", key="api_url")
    st.stop()


# ============================================================================= secondary pages
def page_runs() -> None:
    with st.container(key="panel1"):
        heading("Runs")
        try:
            runs = client().runs()
        except Exception as e:  # noqa: BLE001
            note("bad", f"Could not list runs: {api_error_text(e)}")
            return
        if not runs:
            note("muted", "No comparison has been run yet.")
            return
        left, right = st.columns([3, 1])
        with left:
            table([{"run": r["run_id"], "A": r["release_a"], "B": r["release_b"], "status": r["status"],
                    "verdict": r.get("verdict") or "", "engine": (r.get("detector") or {}).get("name") or "",
                    "created": r["created_at"], "error": (r.get("error") or "")[:90]} for r in runs], max_height=600)
        with right:
            pick = st.selectbox("Open a run", [r["run_id"] for r in runs])
            if st.button("Open on Home", type="primary"):
                st.session_state["run_id"], st.session_state["page"] = pick, "Home"
                st.rerun()


def page_engine() -> None:
    with st.container(key="panel1"):
        left, right = st.columns([1.2, 1])
        with left:
            heading("Detection engine")
            kind = {"configured": "ok", "auto": "ok", "mock": "warn", "not_configured": "bad", "error": "bad"}.get(det_status, "muted")
            note(kind, f"Status: {det_status or 'unknown'}" + (f" · {det.get('name')}" if det.get("name") else ""))
            if det.get("error"):
                note("muted", det["error"])
            for p in health.get("problems", []):
                note("warn", p)
            st.markdown("**How the API finds the engine** (first match wins)\n\n"
                        "1. `CCT_DETECTOR=\"package.module:function\"` or `\"path/to/engine.py:function\"`\n"
                        "2. auto-discovery of `detection/engine.py` exposing `analyze_releases(release_a, release_b, output_path)`\n"
                        "3. `CCT_DETECTOR=mock` for pipeline testing only (results are placeholders)\n\n"
                        "**Contract**: two release folder paths in, a dict with `findings` (shared format v0.2) and optionally "
                        "`analyses`, `repairs`, `verdict` out. Skeleton: `contrib/engine_template.py`.")
        with right:
            heading("Server checks")
            table([{"item": "baseline release (data/tcga-brca/raw)", "value": health.get("baseline_present")},
                   {"item": "releases discovered", "value": health.get("releases_found")},
                   {"item": "format/findings.schema.json", "value": health.get("schema_present")},
                   {"item": "format/validate.py", "value": health.get("validator_present")},
                   {"item": "API version", "value": health.get("version")}])
            st.text_input("API URL", key="api_url")
            kv("Research use only. De-identified, patient-derived data. No clinical claims; repairs are proposals and are never applied automatically.")


def page_mission() -> None:
    with st.container(key="panel1"):
        heading("Mission")
        c1, c2 = st.columns(2)
        c1.markdown(
            "**User:** a research engineer responsible for a dataset that gets new releases.\n\n"
            "**Workflow:** connect two releases of the TCGA-BRCA files, see what changed (sample swaps, duplicate "
            "profiles, membership changes, missing measurements), rerun only the analyses those changes affect "
            "(A1: ER-alpha protein by clinical ER status; A2: PAM50 subtype mix of primary tumors), review proposed "
            "repairs, and export `findings.json` in the shared format v0.2 for a Repair Review Desk team.")
        c2.markdown(
            "**Judging:** an unseen release with the same five files and no RNA, delivered in a sealed envelope. "
            "The tool must find the changes without being told what to look for.\n\n"
            "**Safety:** de-identified, patient-derived research data. No re-identification, no clinical claims, "
            "no automatic repairs: every proposed fix needs a researcher's decision.")


# ============================================================================= home
def page_home() -> None:
    try:
        rels = client().releases()
    except Exception as e:  # noqa: BLE001
        with st.container(key="panel1"):
            note("bad", f"Could not list releases: {api_error_text(e)}")
        return
    names = [r["name"] for r in rels]
    by_name = {r["name"]: r for r in rels}
    try:
        past = client().runs()
    except Exception:  # noqa: BLE001
        past = []

    run_id = st.session_state.get("run_id")
    rec = doc = raw_bytes = tri = None
    if run_id:
        try:
            rec = client().run(run_id)
        except Exception as e:  # noqa: BLE001
            note("bad", f"Run {run_id}: {api_error_text(e)}")
            st.session_state["run_id"] = run_id = None
    if rec and rec["status"] == "completed":
        try:
            doc, raw_bytes = client().findings(run_id)
            tri = client().triage(run_id)
        except Exception as e:  # noqa: BLE001
            note("bad", f"Could not load findings: {api_error_text(e)}")
    summary = (rec or {}).get("summary") or {}
    findings = (doc or {}).get("findings", [])
    analyses = (doc or {}).get("analyses", [])
    repairs = (doc or {}).get("repairs", [])
    decisions = (doc or {}).get("decisions", [])
    decisions_by_repair: dict[str, list[dict]] = {}
    for d in decisions:
        decisions_by_repair.setdefault(d.get("repair_id"), []).append(d)
    triage_available = tri is not None
    repairs_by_finding: dict[str, list[dict]] = {}
    for r in repairs:
        for fid in r.get("addresses", []):
            repairs_by_finding.setdefault(fid, []).append(r)
    run_det = (rec or {}).get("detector") or {}
    auto_ids = {r["id"] for r in (tri or {}).get("repairs", {}).get("automatic", [])}

    def handling(rid: str) -> str:
        if not triage_available:
            return "review (no triage endpoint)"
        return "automatic candidate" if rid in auto_ids else "human review"

    def decision_text(rid: str) -> str:
        return ", ".join(DECISION_LABEL.get(d.get("decision"), str(d.get("decision"))) for d in decisions_by_repair.get(rid, [])) or "pending"

    main_col, side_col = st.columns([2.3, 1], gap="medium")

    # ================================================================ work panel
    with main_col, st.container(key="panel1"):
        t_sel, t_res, t_next, t_info = st.tabs(["Select release", "Results", "Next steps", "Detailed info"])

        # ---------------------------------------------------------- Select release
        with t_sel:
            left, right = st.columns([1.5, 1], gap="large")
            with left:
                if not names:
                    note("bad", "No releases found. Run `python data/tcga-brca/fetch.py`, then `make_release.py` or `envelopes/unseal.py`.")
                c1, c2 = st.columns(2)
                default_a = names.index("baseline") if "baseline" in names else 0
                others = [i for i, n in enumerate(names) if n != "baseline"]
                rel_a = c1.selectbox("Release A (baseline)", names, index=default_a if names else None)
                rel_b = c2.selectbox("Release B (updated)", names, index=(others[-1] if others else 0) if names else None)
                if names:
                    files = list(by_name[names[0]]["files"].keys())
                    picked = [n for n in dict.fromkeys((rel_a, rel_b)) if n]
                    table([{"file": f, **{n: ("present" if by_name[n]["files"].get(f) else "—") for n in picked}} for f in files])
                    table([{"release": by_name[n]["name"], "origin": by_name[n]["origin"], "location": by_name[n]["location"],
                            "required files missing": ", ".join(by_name[n]["missing_required"]) or "none",
                            "RNA file": "yes" if by_name[n]["has_rna"] else "no (not needed)"} for n in picked])
                    for n in picked:
                        if by_name[n]["missing_required"]:
                            note("warn", f"{n} is missing {', '.join(by_name[n]['missing_required'])}; the engine will see it that way.")
                    if rel_a == rel_b:
                        note("muted", "A and B are the same release: a sanity run that should report nothing.")
                if not engine_ready:
                    note("bad", "Compare is disabled: no detection engine is connected (see Engine).")
                elif det_status == "mock":
                    note("warn", "The MOCK engine is connected: a run will produce placeholder output, not findings.")
                if st.button("Compare releases", type="primary", disabled=not (rel_a and rel_b and engine_ready)):
                    try:
                        st.session_state["run_id"] = client().compare(rel_a, rel_b)["run_id"]
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        note("bad", f"Comparison could not start: {api_error_text(e)}")
            with right:
                heading("Current run")
                if not rec:
                    note("muted", "No run selected yet.")
                else:
                    kv(f"{rec['run_id']} · {rec['release_a']} → {rec['release_b']}")
                    if rec["status"] in ("pending", "running"):
                        box = st.empty()
                        deadline = time.time() + 900
                        while time.time() < deadline:
                            last = rec["progress"][-1].split(" ", 1)[-1] if rec.get("progress") else "queued"
                            box.html(f'<div class="cct-note warn">Running · {esc(last)}</div>')
                            time.sleep(1.5)
                            try:
                                rec = client().run(run_id)
                            except Exception as e:  # noqa: BLE001
                                box.html(f'<div class="cct-note bad">{esc(api_error_text(e))}</div>')
                                break
                            if rec["status"] in ("completed", "failed"):
                                st.rerun()
                    elif rec["status"] == "failed":
                        note("bad", f"Run failed: {rec.get('error')}")
                        if (rec.get("validation") or {}).get("errors"):
                            st.code("\n".join(rec["validation"]["errors"]))
                        kv("No findings are shown for a failed run; nothing was substituted.")
                    else:
                        note("ok", f"Completed · verdict {rec.get('verdict') or '—'} · see Results")
                if past:
                    labels = {r["run_id"]: f"{r['run_id']} · {r['release_a']} → {r['release_b']} · {r['status']}" for r in past}
                    ids = list(labels)
                    pick = st.selectbox("Previous runs", ids, index=ids.index(run_id) if run_id in ids else 0, format_func=labels.get)
                    if pick != run_id and st.button("Open selected run"):
                        st.session_state["run_id"] = pick
                        st.rerun()
                with st.expander("Add a release (the five files or one .zip)"):
                    up_name = st.text_input("Name", placeholder="my-release")
                    up_files = st.file_uploader("Files", accept_multiple_files=True, label_visibility="collapsed")
                    if st.button("Upload", disabled=not (up_name and up_files)):
                        try:
                            res = client().upload(up_name, [(f.name, f.getvalue()) for f in up_files])
                            note("ok", f"Stored as {res['name']}; select it above.")
                        except Exception as e:  # noqa: BLE001
                            note("bad", f"Upload rejected: {api_error_text(e)}")
                    kv("On judging day, `python envelopes/unseal.py <n> <code words>` is enough: opened envelopes appear as envelope-<n>.")

        # ---------------------------------------------------------- Results
        with t_res:
            if not doc:
                note("muted", "Run a comparison to see results here.")
            else:
                verdict = doc.get("verdict")
                vk, vt = VERDICT_TEXT.get(verdict, ("muted", "No verdict from the engine."))
                hc = st.columns([1.3, 2.2], vertical_alignment="center")
                with hc[0]:
                    card("Verdict", verdict or "—", vt, flag(vk, run_det.get("name") or "engine"))
                with hc[1]:
                    if run_det.get("mock"):
                        note("bad", "MOCK run: the mock engine produced this output for pipeline testing. Nothing was compared.")
                    v = rec.get("validation") or {}
                    note("ok" if v.get("valid") else "bad",
                         f"findings.json {'passed' if v.get('valid') else 'failed'} {v.get('validator', 'format/validate.py')} · engine {run_det.get('name')}")
                    review_ids = [f["id"] for f in findings if f.get("needs_human_review")]
                    if review_ids or repairs:
                        note("warn", f"Human intervention required: {len(review_ids)} finding(s) flagged for review and "
                                     f"{len(repairs)} proposed repair(s) need a researcher's decision before release B is used.")
                m = summary.get("metrics", {})
                ra, rb = summary.get("release_a", {}), summary.get("release_b", {})
                k = st.columns(8)
                k[0].metric(f"Samples · {ra.get('name', 'A')}", ra.get("samples", "—"), help="Unique sample ids across all files of A")
                k[1].metric(f"Samples · {rb.get('name', 'B')}", rb.get("samples", "—"),
                            delta=(rb.get("samples", 0) - ra.get("samples", 0)) or None, help="Unique sample ids across all files of B")
                k[2].metric("Patients A → B", f"{ra.get('patients', '—')} → {rb.get('patients', '—')}")
                k[3].metric("Ids added / removed", f"{summary.get('samples_added', 0)} / {summary.get('samples_removed', 0)}",
                            help="Whole release: ids in B but in no file of A, and the reverse")
                k[4].metric("Changed in ≥1 file", summary.get("samples_changed_in_any_file", "—"),
                            help="Ids added to or removed from at least one individual file")
                k[5].metric("Sample swaps", m.get("sample_swaps", 0), help=f"{m.get('samples_in_swaps', 0)} sample(s) cited")
                k[6].metric("Duplicates", m.get("duplicate_findings", 0), help=f"{m.get('samples_in_duplicates', 0)} sample(s) cited")
                k[7].metric("Findings", m.get("total_findings", len(findings)),
                            help=" · ".join(f"{KIND_LABEL.get(kk, kk)} {vv}" for kk, vv in (m.get("by_kind") or {}).items()) or None)
                files_tbl = summary.get("files") or {}
                if any(d.get("count_equal_membership_differs") for d in files_tbl.values()):
                    note("warn", "At least one file keeps the same sample count but not the same members (see Detailed info).")

                heading("Findings")
                if not findings:
                    note("muted", "The engine reported no findings for this pair of releases.")
                else:
                    fc = st.columns([1, 1, 1, 1, 2, 1.2], vertical_alignment="bottom")
                    sev_f = fc[0].multiselect("Severity", ["high", "medium", "low", "none"])
                    kind_f = fc[1].multiselect("Type", sorted({f.get("kind", "other") for f in findings}),
                                               format_func=lambda x: KIND_LABEL.get(x, x))
                    conf_f = fc[2].multiselect("Confidence", ["high", "medium", "low"])
                    an_f = fc[3].multiselect("Affects", sorted({a for f in findings for a in f.get("affects_analyses", [])}))
                    q = fc[4].text_input("Search summary, record id or file")
                    review_only = fc[5].checkbox("Review only")

                    def keep(f):
                        if sev_f and f.get("severity") not in sev_f:
                            return False
                        if kind_f and f.get("kind", "other") not in kind_f:
                            return False
                        if conf_f and f.get("confidence") not in conf_f:
                            return False
                        if review_only and not f.get("needs_human_review"):
                            return False
                        if an_f and not set(an_f) & set(f.get("affects_analyses", [])):
                            return False
                        hay = " ".join([f.get("summary", ""), f.get("id", ""), finding_files(f), *records_of(f)]).lower()
                        return not q or q.lower() in hay

                    shown = sorted([f for f in findings if keep(f)], key=lambda f: (SEV_ORDER.get(f.get("severity"), 9), f.get("id", "")))
                    lc, rc = st.columns([1.35, 1], gap="large")
                    with lc:
                        table([{"id": f["id"], "type": KIND_LABEL.get(f.get("kind"), f.get("kind")), "severity": f["severity"],
                                "confidence": f["confidence"], "file": finding_files(f),
                                "records": len(records_of(f)),
                                "cited": ", ".join(records_of(f)[:3]) + (" …" if len(records_of(f)) > 3 else ""),
                                "affects": ", ".join(f.get("affects_analyses", [])) or "—",
                                "not affected": ", ".join(f.get("not_affected_analyses", [])) or "—",
                                "repair": ", ".join(f"{r['id']} {r['action']}" + (" (auto)" if r["id"] in auto_ids else "")
                                                    + (f" [{decision_text(r['id'])}]" if decisions_by_repair.get(r["id"]) else "")
                                                    for r in repairs_by_finding.get(f["id"], [])) or "—",
                                "review": "yes" if f.get("needs_human_review") else "", "summary": f["summary"]} for f in shown],
                              max_height=520)
                        kv(f"{len(shown)} of {len(findings)} findings shown.")
                    with rc:
                        if shown:
                            fid = st.selectbox("Open finding", [f["id"] for f in shown],
                                               format_func=lambda i: f"{i} · {next(f for f in shown if f['id'] == i)['summary'][:80]}")
                            f = next(x for x in shown if x["id"] == fid)
                            with st.container(key=f"subpanel-finding-{fid}"):
                                sev = f["severity"]
                                st.html(f'<div class="cct-h">{esc(f["id"])} · {esc(KIND_LABEL.get(f.get("kind"), f.get("kind")))}</div>'
                                        + flag("bad" if sev == "high" else "warn" if sev == "medium" else "muted", f"severity {sev}")
                                        + flag("muted", f"confidence {f['confidence']}")
                                        + (flag("bad", "human review") if f.get("needs_human_review") else "")
                                        + f'<p>{esc(f["summary"])}</p>'
                                        + (f'<div class="cct-kv">File(s): {esc(finding_files(f))}</div>' if finding_files(f) else ""))
                                table(ev_rows(f["evidence"]), max_height=260)
                                kv("Affects: " + (", ".join(f.get("affects_analyses", [])) or "none")
                                   + " · Not affected: " + (", ".join(f.get("not_affected_analyses", [])) or "none"))
                                for a, why in (f.get("impact_reasons") or {}).items():
                                    kv(f"{a}: {why}")
                                if f.get("limitation"):
                                    note("muted", f"Limitation: {f['limitation']}")
                                for r in repairs_by_finding.get(f["id"], []):
                                    note("warn", f"Proposed repair {r['id']} · {r['action']} · {handling(r['id'])}: {r['justification']}")
                                    for d in decisions_by_repair.get(r["id"], []):
                                        kv(f"Reviewer ({d.get('reviewer_role', '?')}): {DECISION_LABEL.get(d.get('decision'), d.get('decision'))} — {d.get('reason', '')}")
                                if f.get("details"):
                                    with st.expander("Engine details"):
                                        st.json(f["details"], expanded=False)
                st.download_button("Download findings.json", data=raw_bytes, file_name=f"findings-{run_id}.json",
                                   mime="application/json", type="primary", key="dl-results")
                kv(f"Exact file the backend validated. Re-check: python format/validate.py findings-{run_id}.json")

        # ---------------------------------------------------------- Next steps
        with t_next:
            if not doc:
                note("muted", "Proposed repairs and analysis impact appear here after a run.")
            else:
                lc, rc = st.columns([1.2, 1], gap="large")
                with lc:
                    heading("Proposed repairs")
                    if not repairs:
                        note("muted", "The engine proposed no repairs.")
                    else:
                        note("warn", "Every repair is a proposal. The tool never edits a release; a researcher approves, rejects "
                                     "or asks for more evidence.")
                        table([{"id": r["id"], "action": r["action"], "resolves": ", ".join(r.get("addresses", [])),
                                "targets": len(r.get("targets", [])),
                                "handling": handling(r["id"]), "decision": decision_text(r["id"]),
                                "justification": r["justification"]} for r in repairs], max_height=360)
                        rid = st.selectbox("Open repair", [r["id"] for r in repairs])
                        r = next(x for x in repairs if x["id"] == rid)
                        with st.container(key=f"subpanel-repair-{rid}"):
                            st.write(r["justification"])
                            table(ev_rows(r.get("targets", [])), max_height=260)
                            for d in decisions_by_repair.get(rid, []):
                                kv(f"Reviewer decision: {DECISION_LABEL.get(d.get('decision'), d.get('decision'))} by {d.get('reviewer_role', '?')} — {d.get('reason', '')}"
                                   + ("" if d.get("original_preserved") is None else f" · original preserved: {'yes' if d['original_preserved'] else 'no'}"))
                    heading("Reviewer decisions")
                    if decisions:
                        known = {r["id"] for r in repairs}
                        table([{"repair": d.get("repair_id"), "decision": DECISION_LABEL.get(d.get("decision"), d.get("decision")),
                                "reviewer role": d.get("reviewer_role"), "reason": d.get("reason"),
                                "original preserved": {True: "yes", False: "no"}.get(d.get("original_preserved"), "—"),
                                "repair exists": "yes" if d.get("repair_id") in known else "no"} for d in decisions], max_height=260)
                    else:
                        kv("No reviewer decisions yet. A Repair Review Desk adds them to findings.json.")
                with rc:
                    heading("Analysis impact")
                    if not analyses:
                        note("muted", "The engine returned no analyses block (A1/A2 status and before/after results come from the engine).")
                    for a in analyses:
                        status = a.get("status")
                        fk = {"changed": "bad", "unchanged": "ok", "not_rerun": "muted"}.get(status, "muted")
                        with st.container(key=f"subpanel-analysis-{a.get('id')}"):
                            meta = []
                            inputs = a.get("inputs") or (a.get("before") or {}).get("inputs") or (a.get("after") or {}).get("inputs")
                            if inputs:
                                meta.append("inputs: " + ", ".join(inputs))
                            if a.get("reads"):
                                meta.append("reads: " + str(a["reads"]))
                            if a.get("triggered_by"):
                                meta.append("triggered by: " + ", ".join(map(str, a["triggered_by"])))
                            st.html(f'<div class="cct-h">{esc(a["id"])}{" · " + esc(a["title"]) if a.get("title") else ""}</div>'
                                    + flag(fk, status or "?") + flag("muted", "rerun" if status in ("changed", "unchanged") else "not rerun")
                                    + (f'<div class="cct-kv">{esc(" · ".join(meta))}</div>' if meta else ""))
                            if a.get("reason"):
                                st.write(a["reason"])
                            rows = before_after_rows(a)
                            if rows:
                                table(rows, max_height=320)
                            cmp = a.get("comparison") or {}
                            if cmp.get("inputs_added") or cmp.get("inputs_removed"):
                                with st.expander(f"Input samples moved: +{len(cmp.get('inputs_added', []))} / −{len(cmp.get('inputs_removed', []))}"):
                                    st.write({"added": cmp.get("inputs_added", []), "removed": cmp.get("inputs_removed", [])})
                            extra = {kk: vv for kk, vv in cmp.items() if kk not in ("inputs_added", "inputs_removed")}
                            if extra:
                                with st.expander("Comparison details"):
                                    st.json(extra, expanded=False)
                            if a.get("before_error"):
                                note("bad", a["before_error"])

        # ---------------------------------------------------------- Detailed info
        with t_info:
            lc, rc = st.columns(2, gap="large")
            with lc:
                heading("Releases on this server")
                if names:
                    table([{"release": r["name"], "origin": r["origin"], "location": r["location"],
                            "required files missing": ", ".join(r["missing_required"]) or "none",
                            "RNA file": "yes" if r["has_rna"] else "no"} for r in rels], max_height=260)
                if doc:
                    heading("Sample ids per file")
                    table([{"file": f, "ids in A": d.get("samples_a"), "ids in B": d.get("samples_b"),
                            "added": d.get("added"), "removed": d.get("removed"),
                            "same count, different members": "yes" if d.get("count_equal_membership_differs") else "",
                            "note": d.get("error") or ""} for f, d in (summary.get("files") or {}).items()])
                    kv(f"Patients: {summary.get('release_a', {}).get('patients', '—')} in A · "
                       f"{summary.get('release_b', {}).get('patients', '—')} in B (first 12 characters of each sample id). "
                       "Counts come from the files' headers; findings are the engine's.")
                    heading("Run")
                    table([{"item": "run id", "value": rec["run_id"]}, {"item": "engine", "value": run_det.get("name")},
                           {"item": "engine source", "value": run_det.get("source")},
                           {"item": "created", "value": rec["created_at"]}, {"item": "finished", "value": rec.get("finished_at")},
                           {"item": "validator", "value": (rec.get("validation") or {}).get("validator")},
                           {"item": "question", "value": doc.get("question")}])
                    for n in summary.get("notes", []):
                        note("muted", n)
            with rc:
                if doc:
                    heading("Checksums (provenance)")
                    data = doc.get("data", {})
                    if data.get("dataset"):
                        kv(f"Dataset: {data['dataset']}")
                    prod = doc.get("producer", {})
                    kv("Producer: " + " · ".join(f"{kk}: {vv}" for kk, vv in prod.items() if not isinstance(vv, dict)))
                    for r in data.get("releases", []):
                        kv(f"{r['name']} {r.get('role', '')}")
                        table(r["files"], max_height=240)
                    kv("Baseline: hash of the downloaded file (matches data/tcga-brca/sources.csv). Other releases: hash of decompressed content for .gz files.")
                    if (doc.get("producer") or {}).get("engine_producer"):
                        with st.expander("Engine producer block"):
                            st.json(doc["producer"]["engine_producer"], expanded=False)
                    if data.get("engine_data"):
                        with st.expander("Release data as reported by the engine"):
                            st.json(data["engine_data"], expanded=False)
                    with st.expander("Progress log"):
                        st.code("\n".join(rec.get("progress") or []))
                    with st.expander("findings.json"):
                        st.json(doc, expanded=False)
                    st.download_button("Download findings.json", data=raw_bytes, file_name=f"findings-{run_id}.json",
                                       mime="application/json", type="primary", key="dl-info")
                else:
                    note("muted", "Checksums, per-file counts, the run log and the download appear here after a run.")

    # ================================================================ quick-summary panel
    with side_col, st.container(key="panel2"):
        st.markdown("#### Quick summary")
        if doc and not triage_available:
            review_ids = [f["id"] for f in findings if f.get("needs_human_review")]
            hi = bool(review_ids or repairs)
            vk = VERDICT_TEXT.get(doc.get("verdict"), ("muted", ""))[0]
            c = st.columns(2)
            with c[0]:
                card("Verdict", doc.get("verdict") or "—", "", flag(vk, run_det.get("name") or "engine"))
                card("Findings", len(findings),
                     ", ".join(f"{kk} {vv}" for kk, vv in (summary.get("metrics", {}).get("by_severity") or {}).items()) or "none")
            with c[1]:
                card("Human intervention", "required" if hi else "not flagged",
                     f"{len(review_ids)} finding(s) flagged, {len(repairs)} repair(s) to decide",
                     flag("bad" if hi else "ok", "needs a researcher" if hi else "no review flags"))
                card("Risk tier", "—", "needs the /api/runs/{id}/triage endpoint", flag("muted", "not available"))
        elif not tri:
            note("muted", "No completed run selected." if not rec else f"Run {rec['run_id']} is {rec['status']}.")
            c = st.columns(2)
            with c[0]:
                card("Engine", {"mock": "MOCK", "auto": "connected", "configured": "connected"}.get(det_status, "missing"),
                     det.get("name") or "", flag("warn" if det_status == "mock" else "ok" if engine_ready else "bad",
                                                 "testing only" if det_status == "mock" else "ready" if engine_ready else "not configured"))
            with c[1]:
                card("Releases", len(names), ", ".join(names[:4]) + (" …" if len(names) > 4 else ""),
                     flag("ok" if "baseline" in names else "bad", "baseline present" if "baseline" in names else "no baseline"))
        else:
            risk = tri.get("risk") or {}
            vk = VERDICT_TEXT.get(tri.get("verdict"), ("muted", ""))[0]
            hi = tri.get("human_intervention_required")
            c = st.columns(2)
            with c[0]:
                card("Verdict", tri.get("verdict") or "—", "", flag(vk, run_det.get("name") or "engine"))
                card("Findings", tri.get("total_findings", 0),
                     ", ".join(f"{k} {v}" for k, v in (summary.get("metrics", {}).get("by_severity") or {}).items()) or "none")
            with c[1]:
                card("Human intervention", "required" if hi else "not flagged",
                     f"{len(tri.get('findings_needing_review', []))} finding(s), {len(tri['repairs']['review'])} repair(s) to decide",
                     flag("bad" if hi else "ok", "needs a researcher" if hi else "no review flags"))
                card("Risk tier", risk.get("tier", "—"), risk.get("rationale", ""), flag("muted", "placeholder"))
            kv(risk.get("note", ""))
        st.markdown("#### Automatic fixes")
        if doc and not triage_available:
            note("muted", f"Classification needs the backend's /api/runs/{{id}}/triage endpoint, which this API does not expose. "
                          f"All {len(repairs)} proposed repair(s) are listed under Next steps for human review.")
        elif not tri:
            note("muted", "Automatic-fix candidates appear here after a run.")
        else:
            auto = tri["repairs"]["automatic"]
            if not auto:
                note("muted", "No repair qualifies as an automatic candidate; the ones needing review are under Next steps.")
            else:
                kv(f"{len(auto)} candidate(s). Ticking records a choice in this session only; nothing is applied to the data.")
                sel_key = f"autofix-{run_id}"
                st.session_state.setdefault(sel_key, {})
                for r in auto:
                    label = f"{r['id']} · {r['action']} · {r['n_targets']} target(s) · resolves {', '.join(r['addresses'])}"
                    on = st.checkbox(label, value=st.session_state[sel_key].get(r["id"], True), key=f"{sel_key}-{r['id']}")
                    st.session_state[sel_key][r["id"]] = on
                    kv(r["justification"][:170])
                chosen = [k for k, v in st.session_state[sel_key].items() if v]
                kv(f"Selected: {', '.join(chosen) or 'none'}")
        st.markdown("#### Workflow")
        steps = [
            ("Baseline and release B available", bool(names) and len(names) >= 2),
            ("Detection engine connected", engine_ready and det_status != "mock"),
            ("Comparison run completed", bool(rec) and rec["status"] == "completed"),
            ("findings.json passed the official validator", bool(rec) and bool((rec.get("validation") or {}).get("valid"))),
            ("Repairs reviewed by a researcher", bool(decisions)),
            ("findings.json downloaded", False),
        ]
        st.html("".join(f'<div class="cct-note {"ok" if done else "muted"}">{"✓" if done else "○"}&nbsp; {esc(label)}</div>'
                        for label, done in steps))
        kv("Review and download are manual steps and are never marked done by the tool.")
        if past:
            st.markdown("#### Recent runs")
            table([{"run": r["run_id"][-8:], "B": r["release_b"], "status": r["status"], "verdict": r.get("verdict") or ""}
                   for r in past[:6]], max_height=240)


if page == "Runs":
    page_runs()
elif page == "Engine":
    page_engine()
elif page == "Mission":
    page_mission()
else:
    page_home()
