# Cohort Firewall — five product ideas

**The track:** build the trust layer for research data. Software that decides whether data can answer a question, explains why, and catches it when that changes.

**Think product, not report.** Each idea below is a tool someone could install, deploy or plug into their workflow on Monday. Build the **weekend MVP** on this repo's Wisconsin data, and design it so the same tool could later run on any cancer dataset: genomics, proteomics or pathology slides.

**Every Cohort Firewall project must still:** take the question card and return a verdict (Ready, Conditional, Blocked or Insufficient Evidence), with findings linked to rows and fields and a step where a person reviews the result. Give judges **one result they can verify** and **one limitation they can inspect**.

---

## 1 · ReadyCheck: "pytest for datasets"
**The product:** An installable package and command-line tool that runs data-readiness checks the way developers run unit tests, plus a GitHub Action that posts the verdict on every pull request.

**Who uses it:** Data engineers and research teams who change datasets or analysis code.

**Weekend MVP:**
- `readycheck run --question question_card.yaml --data <file>` returns a verdict, `findings.json` and an HTML report.
- 5–8 checks written as plugins: missing values, repeated identifiers, group balance, documentation claims, file version.
- A GitHub Action that runs on every commit and comments the verdict on the pull request. It fails the build if the verdict gets worse.

**Stretch:** a plugin interface so others can add checks; a badge for the README ("Data readiness: Conditional"); adapters for other file formats.

**Demo moment:** Open a pull request that swaps in `practice/P2`. The Action fails, and the comment explains why in plain language.

**Stack:** Python package (Typer or Click), Pandera, Jinja2, GitHub Actions.

## 2 · Provenance Ledger: "git for data lineage"
**The product:** A service that fingerprints every version of a dataset down to individual rows, records each transformation, and can answer "where did this row come from, and what happened to it?"

**Who uses it:** Anyone receiving data from someone else, such as a partner, another lab or a vendor.

**Weekend MVP:**
- Fingerprint the official file and any derived copy: file checksum, plus a hash per row.
- Compare two versions: rows added, removed, reordered or changed.
- Recover lineage when the evidence exists (`practice/P1`). Refuse with a clear "Insufficient Evidence" and what's missing when it doesn't (`practice/P2`).
- A lineage graph view: official file → derived copies → results.

**Stretch:** export lineage in the OpenLineage standard; a "release diff" page for every new data version; attach lineage to each finding automatically.

**Demo moment:** Hand it a file it has never seen. It identifies which rows came from the official file, which were dropped, and what it can't vouch for.

**Stack:** Python, DuckDB, NetworkX or Mermaid for the graph, Streamlit or FastAPI.

## 3 · Multiverse Lab: "every reasonable analysis, at once"
**The product:** A web app where you declare the decisions in an analysis, for example how to treat missing values, repeated codes or uneven groups. It runs every combination and shows which conclusions survive all of them.

**Who uses it:** Researchers and reviewers who need to know whether a headline figure depends on arbitrary choices.

**Weekend MVP:**
- Declare 3–4 decision points in a small YAML file. The app runs every path, which takes seconds with DuckDB.
- A specification-curve chart: every result, sorted, with the choices behind each one.
- A robustness verdict: "this conclusion holds in 100% of reasonable analyses" or "it flips depending on X".
- Feeds the readiness verdict for the question card.

**Stretch:** shareable result links; a "what would change my mind" view; plug in any dataset and question.

**Demo moment:** A judge adds a new decision point live, and the curve and verdict update.

**Stack:** DuckDB, Python, Altair or Plotly, Streamlit.

## 4 · DocTest Agent: "documentation that tests itself"
**The product:** An AI agent that reads dataset documentation, turns each factual claim into an executable check, runs the checks against the data, and sends anything it can't verify to a human review queue.

**Who uses it:** Teams adopting public datasets, where the documentation is often the only source of truth.

**Weekend MVP:**
- An agent reads `breast-cancer-wisconsin.names` and extracts testable claims (counts, ranges, missing values, groups) into a list a person can edit.
- Each claim becomes a check that is run, with a result of pass, fail or untestable, linked to the rows involved.
- A review queue where a person approves, edits or rejects the AI-written checks. Nothing counts until it's approved.
- Every model output is logged, so judges can see what the AI did versus what the person decided.

**Stretch:** works on any README or datasheet; exports the checks as a ReadyCheck plugin (idea 1); runs as a tool other AI agents can call.

**Demo moment:** Paste in a documentation paragraph the agent hasn't seen. It drafts checks, a person approves them, and the results appear.

**Stack:** Any LLM or a local model (no keys committed to the repo), Pandera or Great Expectations, Streamlit or Gradio.

## 5 · Agent Firewall: "permission to use data, for AI agents"
**The product:** A service that AI agents must call before using a dataset for a question. It returns allow, allow-with-conditions, deny or insufficient-evidence, with the evidence attached. It works like a firewall, but for research questions instead of network traffic.

**Who uses it:** Teams building AI research assistants that might otherwise analyse data that can't support the question.

**Weekend MVP:**
- An API (or an MCP server, the standard way to give tools to AI agents) with one main call: `request_use(dataset, question)` → verdict, findings, conditions.
- Rules and checks behind it, from your own code, ReadyCheck or Multiverse Lab.
- A small demo agent that asks the firewall first, then follows its conditions or explains why it stopped.
- An audit log of every request and decision.

**Stretch:** policy files that organisations can edit; human sign-off for "conditional" answers; multiple datasets.

**Demo moment:** Ask the demo agent the question card's question, then a changed question. The firewall's answer changes, and the agent's behaviour changes with it.

**Stack:** FastAPI or an MCP server SDK, Python, any agent framework.

---

## Combine and connect
- **Bigger builds:** ReadyCheck + DocTest Agent, or Provenance Ledger + Agent Firewall.
- **Cross-track demo:** write findings in the shared format (`examples/findings.schema.json`) so an Evidence Navigator team's product can open your results.
- **Next event:** the [Cancer Data Lab](../CANCER_DATA_LAB_PREVIEW.md) will need exactly these tools for genomics, proteomics and pathology data. Build yours to take a dataset adapter.

**Out of scope for every idea:** classifiers, diagnosis, risk scores or clinical claims. Don't commit API keys; let users supply their own or use a local model.
