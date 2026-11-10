# Cohort Firewall — five project ideas

**The track in one line:** decide whether data can answer a question, and show what would change that decision.

These are starting points, not assignments. Combine them, change them, or build something else. Whatever you build, give judges **one result they can verify** and **one limitation they can inspect**.

Every idea uses the files in this repo: `data/wisconsin_readable.csv` (start here), the official `data/breast-cancer-wisconsin.data` and `.names`, the cases in `practice/`, and the optional shared format in `examples/`.

---

## 1 · Readiness Report Generator
**Problem:** Reviewers get a dataset and a question, but no structured answer to "can we use this?"
**Build:** A command-line tool or notebook that takes the question card and the data and produces a verdict (Ready, Conditional, Blocked or Insufficient Evidence), a list of findings, and a one-page HTML report.
**Show judges:** Run it live on the official file. Then change one line of the question and show the verdict update.
**Tools:** pandas or DuckDB; Pandera for checks; Jinja2 or Quarto for the report.
**Effort:** Good first project. Strong on *Finding data problems* and *Working tool*.

## 2 · Provenance Guard
**Problem:** Files get sorted, filtered and "cleaned" as they're passed around. A tool that trusts row order or labels can silently produce wrong results.
**Build:** A checker that confirms which version of the data it's looking at (checksum, row count, `source_row`), recovers group labels when the evidence allows, and refuses with a clear reason when it doesn't.
**Show judges:** Run it on `practice/P1` (recovers) and `practice/P2` (returns Insufficient Evidence, with what would resolve it).
**Tools:** Python `hashlib`, pandas; optional: a small rules file listing what each check requires.
**Effort:** Medium. Strong on *Evidence and sources* and *Safety and uncertainty*.

## 3 · What-If Engine
**Problem:** A headline figure depends on choices: what to do with missing values, repeated codes, or uneven groups. Nobody shows whether those choices change the conclusion.
**Build:** A tool that runs every reasonable combination of handling choices and shows which conclusions hold under all of them and which flip.
**Show judges:** One chart or table: each choice, its result, and whether the decision changes.
**Tools:** pandas with `itertools.product`; Altair or Plotly; DuckDB if you prefer SQL.
**Effort:** Medium. Strong on *Reasoning for the research question* and *Useful next steps*.

## 4 · Documentation Cross-Checker
**Problem:** Dataset documentation makes claims (counts, ranges, where values are missing, class balance) that nobody tests against the actual file.
**Build:** A tool that turns statements in `breast-cancer-wisconsin.names` into testable checks, runs them against the data, and reports which ones hold, which fail, and which can't be tested.
**Show judges:** The list of documented claims with a pass, fail or untestable result for each, linked to the rows involved.
**Tools:** pandas; Great Expectations or plain assertions. An AI model can draft the checks from the text, as long as a person reviews them and the tool shows which claims the model extracted.
**Effort:** Medium to hard. Strong on *Finding data problems* and *Evidence and sources*.

## 5 · Data Readiness Gate for every commit
**Problem:** Datasets change. A new release can quietly break an analysis that used to be fine.
**Build:** Readiness checks that run automatically, like tests, whenever the data or analysis changes, and block a merge if the verdict gets worse.
**Show judges:** Swap in a practice file as a "new release" and show the gate catch it, with a readable explanation.
**Tools:** pytest, GitHub Actions, Pandera.
**Effort:** Medium. Strong on *Working tool and clear setup* and *Useful next steps*. Good preparation for the Cancer Data Lab's "The Result Changed" finale.

---

**Pairing with Evidence Navigator:** if your tool writes findings in the shared format (`examples/findings.schema.json`), an Evidence Navigator team can open your results in their tool. That's optional, but it makes a strong demo.

**Out of scope for every idea:** classifiers, diagnosis, risk scores or clinical claims.
