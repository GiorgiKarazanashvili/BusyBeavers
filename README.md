# OncoSys Cancer AI Lab: Healthcare AI Hackathon

![A real breast cancer slide from TCGA (left) beside an AI model's map of where immune cells are likely (right)](assets/hero_tissue_ai.jpg)

**Left:** a real H&E slide from TCGA (patient TCGA-OL-A5RW). **Right:** a published AI model's estimate of where tumor-infiltrating lymphocytes are. Its highest patch probability is 0.63, and at its own threshold it calls just one patch positive. **Is that result right, and how would anyone check?** That's what you'll build tools for.

<p>
<a href="data/README.md"><img alt="Explore the data" src="https://img.shields.io/badge/%E2%91%A0%20Explore%20the%20data-0b6e99?style=for-the-badge"></a>
<a href="products/README.md"><img alt="Pick a mission" src="https://img.shields.io/badge/%E2%91%A1%20Pick%20a%20mission-7a3e9d?style=for-the-badge"></a>
<a href="https://colab.research.google.com/github/disleveK/oncosys-hackathon-challenge/blob/main/starter/tcga_starter.ipynb"><img alt="Run the starter" src="https://img.shields.io/badge/%E2%91%A2%20Run%20the%20starter-1a7f37?style=for-the-badge"></a>
</p>

- **Explore the data:** seven data packs (tumor molecular data, tissue images, CT scans, cell lines, trial records) plus a 30-minute warm-up. The menu shows included starters, source downloads and viewer links.
- **Pick a mission:** six featured products and optional custom builds, across two tracks.
- **Run the starter:** in 15 minutes, download real tumor data, see how each join shrinks the cohort, and open a slide in your browser.

## Pick a user, build one workflow
| Track | What it does | Featured products |
|---|---|---|
| **Cohort Firewall** | Catches what could make a result unreliable | [Cohort Control Tower](products/cohort-control-tower.md) · [Cohort Studio](products/cohort-studio.md) |
| **Evidence Navigator** | Helps someone investigate a result and decide what to do | [Multimodal Case Room](products/multimodal-case-room.md) · [Evidence Copilot](products/evidence-copilot.md) · [Research Claim Auditor](products/research-claim-auditor.md) · [Repair Review Desk](products/repair-review-desk.md) |

Build a web app, an AI agent, a visual workflow, or a tool that plugs into a notebook. You can also combine two products or [pitch your own](products/README.md#pitch-your-own-lighter-support).

**The bar:** a judge can use your workflow without you narrating, and it shows **one result they can verify** and **one limitation they can inspect.**

**The finale:** a Cohort Control Tower catches a silent change in a new data release, and a different team's Repair Review Desk receives the findings and makes the review decision, live, through the [shared format](format/README.md).

## The data packs
| Pack | One record is… | Status |
|---|---|---|
| [TCGA breast cancer](data/tcga-brca/README.md) *(core)* | A tumor sample with clinical, survival, mutation, copy number, RNA and protein data, plus slide links | Ready |
| [Pathology: PathMNIST](data/pathmnist/README.md) | A labelled colorectal tissue patch | Ready |
| [Molecular + imaging: CPTAC](data/cptac/README.md) | A lung, colon or kidney cancer case | Ready: protein, slides and CT links |
| [Imaging: LIDC-IDRI](data/lidc-idri/README.md) | A chest CT with radiologists' nodule marks | Ready |
| [Prediction: DepMap](data/depmap/README.md) | A cancer cell line | Ready |
| [Trial records: ClinicalTrials.gov](data/clinical-trials/README.md) | A dated trial record + fictional cases | Ready for practice |
| [Advanced: CAMELYON17](data/camelyon17/README.md) | A lymph-node slide from one of 5 hospitals | Ready (source-linked) |

**Only join records where a documented match exists.** Tissue patches, cell lines, tumor samples and CT scans describe different things. See [the joining rule](data/README.md#the-joining-rule).

## What's in this repo
| Path | What it is |
|---|---|
| `starter/tcga_starter.ipynb` | The 15-minute starter |
| `products/` | Six featured product briefs, practice inputs, and pitch-your-own ideas |
| `data/` | Seven data packs: each with a README, sources and checksums, fetch script, and manifests |
| `assets/` | The challenge page image |
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
