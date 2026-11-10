# OncoSys Cancer AI Lab: Healthcare AI Hackathon

## Does the protein agree with the pathology report?
Breast tumors are tested for estrogen receptor (ER) in the clinic, and TCGA also measured the ER-alpha protein directly. Of 1,101 primary tumors, only 535 have every data layer, and each join changes who is in the cohort. **Real cancer evidence comes from different sources that don't always line up. Build the tools that catch it and help people decide what to do.**

**Start here:** [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/disleveK/oncosys-hackathon-challenge/blob/main/starter/tcga_starter.ipynb) or open [`starter/tcga_starter.ipynb`](starter/tcga_starter.ipynb). In 15 minutes it downloads the data, explains what one row means, shows how the cohort shrinks with each join, and opens a pathology slide in your browser.

## Pick a user, build one workflow
| Track | What it does | Featured products |
|---|---|---|
| **Cohort Firewall** | Catches what could make a result unreliable | [Cohort Control Tower](products/cohort-control-tower.md) · [Cohort Studio](products/cohort-studio.md) |
| **Evidence Navigator** | Helps someone investigate a result and decide what to do | [Multimodal Case Room](products/multimodal-case-room.md) · [Evidence Copilot](products/evidence-copilot.md) · [Research Claim Auditor](products/research-claim-auditor.md) · [Repair Review Desk](products/repair-review-desk.md) |

Build a web app, an AI agent, a visual workflow, or a tool that plugs into a notebook. You can also combine two products or [pitch your own](products/README.md#pitch-your-own-lighter-support).

**The bar:** a judge can use your workflow without you narrating, and it shows **one result they can verify** and **one limitation they can inspect.**

**The finale:** a Cohort Control Tower catches a silent change in a new data release, and a different team's Repair Review Desk receives the findings and makes the review decision, live, through the [shared format](format/README.md).

## The data: TCGA breast cancer, one patient, many views
| Layer | Coverage |
|---|---|
| Clinical records (194 fields) and curated survival | 1,101 patients, 1,247 samples |
| Mutations, copy number, RNA, protein | 747 to 1,218 samples, depending on the layer |
| Pathology slides, viewable in the browser | 3,111 slides (1,133 diagnostic, 1,978 frozen) |

Details, IDs and download: [`data/tcga-brca/`](data/tcga-brca/README.md). Adding a dataset: [`data/README.md`](data/README.md).

## What's in this repo
| Path | What it is |
|---|---|
| `starter/tcga_starter.ipynb` | The 15-minute starter |
| `products/` | Six featured product briefs, practice inputs, and pitch-your-own ideas |
| `data/tcga-brca/` | Fetch script with frozen checksums, sample and slide manifests, reference analyses, release generator |
| `format/` | Shared findings format v0.2, validator and reference output |
| `warmup/wisconsin/` | Optional 30-minute warm-up on a small dataset |
| [`RULES.md`](RULES.md) · [`DATA_LICENSES.md`](DATA_LICENSES.md) | What's allowed, and how to credit the data |
| [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) | What to check before the code freeze |

## Run it on your computer
```bash
git clone https://github.com/disleveK/oncosys-hackathon-challenge.git
```
```bash
cd oncosys-hackathon-challenge
```
```bash
pip install -r requirements.txt
```
```bash
python data/tcga-brca/fetch.py
```
```bash
jupyter notebook starter/tcga_starter.ipynb
```

## Recommended tools
Use any stack. Start with the smallest toolset that lets someone else rerun your work. No paid account, hosted app, or AI coding assistant is required.

| Task | Optional tools | What to practice |
|---|---|---|
| Read and check the data | [pandas](https://pandas.pydata.org/), [Polars](https://docs.pola.rs/), or [DuckDB](https://duckdb.org/). For repeatable checks, try [Pandera](https://pandera.readthedocs.io/) or [Great Expectations](https://docs.greatexpectations.io/). [ydata-profiling](https://docs.profiling.ydata.ai/) can help with initial exploration. | Keep sample and patient IDs separate. Record the release, checksums, checks run, and affected samples. Treat a profile report as a starting point, not a verdict. |
| Compare figures | A notebook or SQL is enough. | Compare figures with their denominators. Test whether reasonable choices about which samples to include change the conclusion. |
| Work with slides | NCI Imaging Data Commons viewer links in `slide_manifest.csv`; [`idc-index`](https://pypi.org/project/idc-index/) to download | Distinguish diagnostic from frozen slides. Link a slide to a case only when its barcode matches. |
| Build a reviewer interface | [Streamlit](https://docs.streamlit.io/get-started) or [Gradio](https://www.gradio.app/docs). Try [axe-core](https://github.com/dequelabs/axe-core) or [Lighthouse](https://developer.chrome.com/docs/lighthouse/) for accessibility checks. | Make it possible to trace a headline number to its evidence and reach a decision without the presenter. Test keyboard navigation and whether labels make sense without color. |
| Use AI responsibly | Any LLM or a local model. Users supply their own key; never commit one. | Let the AI run real queries rather than answer from memory. Show its sources. Make it say when the data can't answer. |
| Document provenance | The [shared format](format/README.md), a Markdown evidence log, or [W3C PROV](https://www.w3.org/TR/prov-overview/) as background | For each claim, record the release, samples, calculation, limitation, and who should review it. |
| Check for secrets | [Gitleaks](https://github.com/gitleaks/gitleaks), manually or in pre-commit | Before submitting, check for credentials, tokens, private URLs and restricted files. |

## Source and citation
TCGA data from the UCSC Xena TCGA hub and NCI Imaging Data Commons; full credits in [`DATA_LICENSES.md`](DATA_LICENSES.md). The data is de-identified but patient-derived: research use only, no re-identification, no clinical claims.
