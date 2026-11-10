# Preview: the OncoSys Cancer Data Lab

**This is a preview. It isn't part of this weekend's scoring, and the data packs below aren't available to download yet.** This weekend's challenge uses the Wisconsin data in this repository.

## The idea
Real cancer research means connecting different kinds of evidence (proteins, RNA, images, trial rules) and working out what those connections actually support. The Cancer Data Lab will give you a shared starting kit and let you choose what to build.

**The one rule:** build anything you want, but give a judge **one result they can verify** and **one limitation they can inspect**. Notebooks, dashboards, command-line tools, AI agents and visual workflows are all welcome.

## Planned mission packs
| Mission | Data (planned) | What you could build |
|---|---|---|
| **Protein evidence** | CPTAC pan-cancer proteomics, starting with lung, colorectal and kidney cancer, with matched RNA where verified | An explorer that shows where RNA and protein disagree, and what that does to a conclusion |
| **Cell-line prediction** | Broad DepMap expression, CRISPR and drug-response data | A model that ranks cell lines by sensitivity, tested on held-out lines. A cell-line result says nothing by itself about patients. |
| **Imaging** | CPTAC lung adenocarcinoma radiology and pathology images (Imaging Data Commons) | A reviewer that opens the tissue image behind a finding |
| **Trial rules** | ClinicalTrials.gov eligibility criteria and record history, with fictional cases | A tool that shows why fictional cases move in or out of a research cohort when the criteria change |

## The same two tracks
| Track | What every project must prove | Example products |
|---|---|---|
| **Cohort Firewall** | Which samples can answer a question, and how a change in the data affects the result | A cohort builder that checks patient-to-sample joins; a monitor that catches a new release dropping a cancer subtype; a model tester that shows what happens when protein data is missing |
| **Evidence Navigator** | That a reviewer can trace a claim to the data, reproduce it, and see where it stops being supported | A protein evidence explorer; a pathology viewer linked to the sample behind a claim; a trial-criteria assistant that highlights what changed |

## A finale we're designing: "The Result Changed"
Judges hand each team a new data release: same number of samples, but some have changed and one cancer type has lost its protein data. The team reruns its tool and shows which conclusions still hold. Then a reviewer opens that result in a different team's Navigator, using the shared [findings format](examples/findings.schema.json).

**Want to get ready?** Build your tool this weekend so it reads the shared findings format and reruns cleanly when the data changes. That's the skill the Cancer Data Lab rewards.
