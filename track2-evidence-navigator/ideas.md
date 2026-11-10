# Evidence Navigator — five product ideas

**The track:** build the decision layer for research evidence. Software that lets a person reach a decision, trace it to the data, and see where the evidence stops.

**Think product, not slide.** Each idea below is a tool a research team could use on Monday. Build the **weekend MVP** on this repo's data and the findings you receive at kickoff. Until then, build against `examples/findings.example.json` and `data/wisconsin_readable.csv` (use `source_row` to link back to the official file). Design it so it could later handle genomics, proteomics or pathology evidence.

**Every Evidence Navigator project must still:** let a judge complete the decision scenario (proceed, fix a problem, narrow the question, or stop) without your help, link each conclusion to evidence or mark it as interpretation, and show when a person must review. Give judges **one result they can verify** and **one limitation they can inspect**.

---

## 1 · Evidence Passport SDK: "every number carries its proof"
**The product:** A reusable component that any dashboard, notebook or web page can use to display a number. Clicking it opens the number's "passport": calculation, source rows, data version and limitations. It can even **rerun the calculation in the browser**.

**Who uses it:** Anyone publishing research figures, from dashboard builders to report writers.

**Weekend MVP:**
- A web component or Streamlit component, for example `<evidence-number src="findings.json" id="F1">`.
- The passport panel: calculation, the exact source rows (from `source_row`), file checksum, limitations and reviewer.
- A "Reproduce" button that recomputes the number in the browser (DuckDB-WASM or Pyodide) and shows a match or mismatch.
- A demo dashboard built with it that walks through the decision scenario.

**Stretch:** an npm or pip package; a version for Jupyter; passports that update when the data version changes.

**Demo moment:** A judge clicks the headline number, hits Reproduce, and gets the same figure from the raw rows without your help.

**Stack:** TypeScript or Svelte web component (or a Streamlit custom component), DuckDB-WASM or Pyodide.

## 2 · Decision Room: "a pull request for data decisions"
**The product:** A collaborative workspace where a data decision is proposed, reviewed by different roles, discussed and signed off, with a permanent record of who decided what and why.

**Who uses it:** Research groups and data-use committees, the people who have to say yes or no.

**Weekend MVP:**
- Load the findings and the decision scenario. Four role views (engineer, researcher, data-use reviewer, program leader) over the same facts. Switching roles never changes the numbers.
- Comments attached to individual findings; a required sign-off step.
- A final decision record exported as Markdown, PDF or JSON: option chosen, reasons, limitations, reviewers and timestamps.

**Stretch:** real-time collaboration; notifications in Slack or Discord; a decision history timeline; reopening a decision when new evidence arrives.

**Demo moment:** Two judges take different roles, disagree in comments, and reach a signed decision that exports as a complete record.

**Stack:** Next.js or SvelteKit with SQLite or Supabase, or Streamlit with a small database.

## 3 · Honest Charts: "a chart library that warns you"
**The product:** A charting tool that notices when a summary hides something, such as a pooled figure covering very different groups, small denominators or missing data, and says so on the chart itself.

**Who uses it:** Anyone who builds charts for decision-makers.

**Weekend MVP:**
- A chart builder or wrapper (for example around Altair or Plotly) that takes a dataset and a grouping column.
- Automatic checks before it draws: do groups differ a lot? Are some groups tiny? Is data missing? When a check trips, the chart adds a warning and offers the grouped view.
- Always shows denominators; accessible by default, with keyboard support, text alternatives and colour-blind-safe palettes.
- Used to build the visual answer to the decision scenario.

**Stretch:** a Python package; a "lint my chart" mode for existing charts; plug-ins for notebooks and dashboards.

**Demo moment:** Ask it for the pooled chart. It draws it, flags what the pooled view hides, and one click shows the alternative.

**Stack:** Python, Altair or Plotly, pandas; axe-core or Lighthouse for accessibility checks.

## 4 · Evidence Court: "settle disagreements with evidence"
**The product:** A workflow app where conflicting claims become "cases". Each side's evidence is laid out side by side, an AI clerk summarises with citations, and a person rules, recording what evidence would change the ruling.

**Who uses it:** Teams where analysts disagree, which is most teams.

**Weekend MVP:**
- Open a case from two or more findings that point different ways, or from a new claim typed in.
- An evidence map: which rows and checks support each side, and which don't.
- An AI clerk that summarises each side **only from the attached evidence**, quoting it, and lists what's missing to decide.
- A ruling form that records the decision, the reasons, and "what would change this".

**Stretch:** cases linked to the Decision Room; reopening a case automatically when the data changes.

**Demo moment:** A judge adds a new, conflicting claim live. The app opens a case, places the claim next to the existing evidence, and shows what would settle it.

**Stack:** Streamlit or a small web app, the shared findings format, any LLM or local model (no keys in the repo).

## 5 · Grounded Copilot: "an AI analyst that can't bluff"
**The product:** A chat assistant that answers questions by actually running queries on the data, cites the source rows for every answer, and refuses when the evidence doesn't support an answer. It comes with an evaluation suite that proves it.

**Who uses it:** Program leaders and reviewers who want answers in plain language without trusting a black box.

**Weekend MVP:**
- A chat interface where the assistant uses tools: run a query in a sandbox (DuckDB or pandas), read findings, look up the documentation.
- Every answer shows its citations: rows, query and finding IDs. Unsupported questions get a clear refusal that explains what's missing.
- An **evaluation suite**: 20 test questions (supported, unsupported and trick questions) with a score for correct answers and correct refusals.
- Runs without your API key: use a local model, or let the user paste their own key.

**Stretch:** a Slack or Discord bot; a voice mode for program leaders; an MCP server so other agents can ask it questions.

**Demo moment:** A judge asks one supported question (cited answer) and one that sounds reasonable but isn't supported (refusal with reasons). Then show the evaluation score.

**Stack:** any LLM with tool use or a local model, DuckDB, Streamlit or Gradio chat.

---

## Combine and connect
- **Bigger builds:** Decision Room + Evidence Passport SDK, or Grounded Copilot + Evidence Court.
- **Cross-track demo:** read the shared findings format (`examples/findings.schema.json`) so you can open a Cohort Firewall team's results directly in your product.
- **Next event:** the [Cancer Data Lab](../CANCER_DATA_LAB_PREVIEW.md) will link claims to proteins, genes and pathology slides. Build your evidence model so a source can be a row, a gene or an image region.

**Out of scope for every idea:** classifiers, diagnosis, risk scores or clinical claims. Don't commit API keys; let users supply their own or use a local model.
