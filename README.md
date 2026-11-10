# OncoSys AI Healthcare Hackathon — event data

**Dataset:** Breast Cancer Wisconsin (Original), UCI Machine Learning Repository. Frozen for this event as `v1.0.0`.

**This is a data-readiness exercise. Classifiers, diagnosis and clinical claims are out of scope.**

## The shared question
A reviewer wants to report one malignant share across all eight collection groups. Should they report the pooled figure, show group results alongside it, or pause? Show the evidence behind your decision and explain what the data can support.

| Track | Brief | What you build |
|---|---|---|
| **Cohort Firewall** | `track1-cohort-firewall/` | A tool that audits the data for the question and returns Ready, Conditional, Blocked or Insufficient Evidence, with the evidence behind it |
| **Evidence Navigator** | `track2-evidence-navigator/` | An interactive tool that helps four kinds of users understand the findings and make the publishing decision |

The full rules and the scoring rubric for each track are in the challenge package.

## Files
| Path | What it is |
|---|---|
| `data/breast-cancer-wisconsin.data` | **Official data.** 699 rows, no header row; `?` means missing |
| `data/breast-cancer-wisconsin.names` | UCI's documentation. Read sections 4, 7 and 8. |
| `SHA256SUMS` | Checksums for the official files. Verify before you start. |
| `starter/starter.ipynb` | Loads the data, verifies checksums and derives collection groups |
| `practice/` | Two practice cases for testing how your tool handles provenance. Not for judged results. |
| `examples/` | An optional shared findings format and a worked example |
| `SUBMISSION_CHECKLIST.md` | What to check before the code freeze |

## Quick start
**Option A — your computer**
```bash
git clone https://github.com/disleveK/oncosys-hackathon-challenge.git
```
```bash
cd oncosys-hackathon-challenge
```
```bash
sha256sum -c SHA256SUMS
```
On macOS, use `shasum -a 256 -c SHA256SUMS`.
```bash
pip install pandas jupyter
```
```bash
jupyter notebook starter/starter.ipynb
```

**Option B — no install:** [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/disleveK/oncosys-hackathon-challenge/blob/main/starter/starter.ipynb). The notebook downloads and verifies the data itself.

## Practice cases
Test your tool on [`practice/`](practice/README.md) before Saturday:
- **P1:** a sorted copy where collection groups can be recovered.
- **P2:** an extract where the evidence to recover them is missing, so **Insufficient Evidence** is the right answer for group-level questions.

The judging cases are different and stay private.

## Shared findings format (optional)
A Cohort Firewall tool produces findings; an Evidence Navigator tool turns findings into a decision a reviewer can trace. If you'd like your tool to work with others, write or read [`examples/findings.schema.json`](examples/findings.schema.json). See the [worked example](examples/findings.example.json). It isn't required for judging.

## Before you submit
Work through [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md). The code freeze is **Saturday, November 14, 2:15 PM ET**.

## Recommended tools

Use any stack. Start with the smallest toolset that lets someone else rerun your work. No paid account, hosted app, or AI coding assistant is required.

| Task | Optional tools | What to practice |
|---|---|---|
| Read and check the data | [pandas](https://pandas.pydata.org/), [Polars](https://docs.pola.rs/), or [DuckDB](https://duckdb.org/). For repeatable checks, try [Pandera](https://pandera.readthedocs.io/) or [Great Expectations](https://docs.greatexpectations.io/). [ydata-profiling](https://docs.profiling.ydata.ai/) can help with initial exploration. | Preserve the original source row number before sorting or filtering. Record the dataset version, checks run, and affected rows or fields. Treat a profile report as a starting point, not a verdict. |
| Compare figures | A notebook or SQL is enough. A chi-square test is optional if its assumptions are justified. | Compare pooled and group-level figures with denominators. Test whether reasonable choices about duplicates and missing values change the conclusion. Don't infer demographic bias from fields that aren't present. |
| Build a reviewer interface | [Streamlit](https://docs.streamlit.io/get-started) or [Gradio](https://www.gradio.app/docs). Try [axe-core](https://github.com/dequelabs/axe-core) or [Lighthouse](https://developer.chrome.com/docs/lighthouse/) for accessibility checks. | Make it possible to trace a headline number to its evidence and reach a decision without the presenter. Test keyboard navigation and whether labels and verdicts make sense without color. |
| Document provenance | A Markdown evidence log or JSON record works. [W3C PROV](https://www.w3.org/TR/prov-overview/) is optional background. | For each claim, record the source file and version, row or group selection, calculation, limitation, and who should review it. Collection groups are derived from UCI documentation, not recorded in the raw file. |
| Check for secrets | [Gitleaks](https://github.com/gitleaks/gitleaks), manually or in pre-commit. | Before submitting, check the repository for credentials, tokens, private URLs, and restricted files. |

## Source and citation
Collected by Dr. William H. Wolberg, University of Wisconsin Hospitals, Madison, 1989–1991; donated to UCI on 15 July 1992.
Cite: Wolberg, W. (1990). *Breast Cancer Wisconsin (Original)* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5HP4Z
Dataset license: [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/), as listed on the [UCI dataset page](https://archive.ics.uci.edu/dataset/15). This license statement applies to the UCI dataset. The starter notebook derives collection groups from UCI’s documented row boundaries; those labels are not fields in the source data.

The data is de-identified but patient-derived. Don't attempt to re-identify anyone or link it to other sources.
