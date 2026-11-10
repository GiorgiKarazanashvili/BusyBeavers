# Preview: the OncoSys Cancer Data Lab

**This is a preview. It isn't part of this weekend's scoring, and the data kits below aren't available to download yet.** This weekend's challenge uses the Wisconsin data in this repository.

## How it works
Pick a user. Build **one workflow that user can finish**, and demo it on real research data. Build a web app, an AI agent, a visual workflow, or a tool that plugs into an existing notebook.

- **Cohort Firewall** catches what could make a result unreliable.
- **Evidence Navigator** helps someone investigate the result and decide what to do.

**The bar:** a judge can use your workflow without you narrating it, and it shows one result they can verify and one limitation they can inspect.

Each product will come with a small starter dataset, a runnable example, sample model outputs (so you don't have to train anything), and a shared format for handing results to other teams' products. Build one product, combine two, or pitch your own.

## Ten products a cancer research team would want

### Cohort Firewall
| Product | User and workflow | Planned data |
|---|---|---|
| **Cohort Control Tower** | A research engineer connects two releases of a dataset. The tool spots sample swaps, duplicate patients and missing measurements, then reruns only the analyses those changes affect. | CPTAC proteomics and clinical data |
| **Cohort Studio** | A researcher describes a cohort in plain English or on a visual canvas. The tool turns it into editable filters and joins, shows how many records survive each step, and exports a rerunnable workflow. | CPTAC RNA, protein and sample metadata |
| **Model Crash Lab** | A computer vision team plugs in a tissue classifier. The lab runs it on original and altered images, finds its worst failure mode, and recommends images for manual review. | Public colorectal tissue patches (PathMNIST / NCT-CRC-HE) |
| **Benchmark Builder** | A team builds an evaluation service for cell-line predictions that catches overlapping cell lines, creates a documented split and compares against a simple baseline. | Broad DepMap |
| **Amendment Replay Engine** | A trial research team compares two versions of eligibility rules. AI proposes structured rules, a person corrects them, and the engine reruns a fictional cohort to show who moved in, out, or needs review. | ClinicalTrials.gov record history with fictional cases |

### Evidence Navigator
| Product | User and workflow | Planned data |
|---|---|---|
| **Evidence Copilot** | A scientist asks a question. The assistant runs a bounded analysis and returns a chart with its source release, filters, sample count and calculation attached, and says what it couldn't establish. | CPTAC proteomics |
| **Pathology Search and Review** | A reviewer starts from a tissue patch, finds similar examples, and sends uncertain results to a review queue, keeping the original prediction alongside the correction. | Tissue patches, precomputed image embeddings and model predictions |
| **Multimodal Case Room** | A research team opens one case and sees its slide or scan, sample metadata and molecular evidence together, with an AI brief linked to each source. It refuses to attach an image it can't verify. | CPTAC lung adenocarcinoma slides and CT (NCI Imaging Data Commons) with molecular data |
| **Research Claim Auditor** | A reviewer uploads a report. The agent extracts claims and sorts them into supported, contradicted, or insufficient evidence, each with its calculation. | CPTAC data and an organizer-written research brief |
| **Repair Review Desk** | A reviewer receives a proposed cohort or data repair from a Firewall tool, sees which findings move, and approves, rejects or asks for more evidence, keeping the original analysis. | Output from any Firewall product |

## The finale: tools that work together
- **Cohort Control Tower → Repair Review Desk.** One team catches a silent change in a research cohort. A second team, using its own product, receives the finding, sees which conclusions moved, and records a review decision.
- **Model Crash Lab → Pathology Search and Review.** One team finds where a model fails. Another team's reviewer investigates those failures and corrects them.

**Want to get ready?** Build this weekend's tool so it reads and writes the shared [findings format](examples/findings.schema.json) and reruns cleanly when the data changes.

*Classifiers in the Cancer Data Lab are research tools on public patches and cell lines, judged on robustness and honesty. No diagnosis, treatment recommendations or clinical claims.*
