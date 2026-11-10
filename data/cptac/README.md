# Molecular and imaging pack: CPTAC (lung, colon, kidney)

**One record = one CPTAC case (a patient) with tissue slides and, where available, protein, RNA and clinical data.** CPTAC measured protein directly by mass spectrometry, so it's the best public source for comparing RNA and protein evidence.

## What's ready now
| File | What it is | Rows |
|---|---|---|
| `slide_manifest.csv` | Every CPTAC slide in NCI Imaging Data Commons: cohort, case, slide, size, license, **browser viewer link** | 2,291 slides (244 lung, 178 colon, 222 kidney cases) |
| `lung_ct_manifest.csv` | CT studies for lung cases, with viewer links | 37 cases |

Slides and scans stay at the source. Open them in the browser from the `viewer_url` column; download with `idc-index` only if you need pixels.

## What's still being verified: protein and RNA
The protein extract (selected proteins and sample metadata for the three cohorts) comes from the [NCI Proteomic Data Commons](https://pdc.cancer.gov). It **isn't in this pack yet**, because the organizers couldn't reach PDC from the environment used to build it. When it's added, it will follow the same pattern as `../tcga-brca/`: `sources.csv` with checksums, `fetch.py`, and a sample manifest.

RNA will be added **only for samples whose match to the protein sample is verified.**

## Matching IDs: read this before joining anything
| Cohort | Case ID format in the slide manifest | Note |
|---|---|---|
| Lung | 240 cases `C3L-`/`C3N-` + **4 non-standard** (for example `11LU013`) | The 4 non-standard IDs won't match protein records without a documented mapping |
| Kidney | All `C3L-`/`C3N-` | |
| Colon | **All 178 non-standard** | Needs a documented mapping before any join |

The `id_format` column flags each case. **Only join records where a documented match exists**; otherwise show the gap. That's a feature for the Multimodal Case Room, not a bug.

## What it opens up
Cohort builders across three cancer types, data-quality monitors, RNA-versus-protein disagreement explorers, and case workspaces linking a finding to its tissue.

## Source and license
NCI Imaging Data Commons collections `cptac_luad`, `cptac_coad`, `cptac_ccrcc` (CC BY 4.0). Credit the Clinical Proteomic Tumor Analysis Consortium (CPTAC) and NCI Imaging Data Commons. Patient-derived and de-identified: no re-identification, no clinical claims.
