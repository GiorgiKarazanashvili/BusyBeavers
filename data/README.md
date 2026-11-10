# Explore the data

The packs are a menu. Start small; larger datasets and heavier models are optional.

| Pack | One record is… | Laptop download | What it opens up | Status |
|---|---|---|---|---|
| **[TCGA breast cancer](tcga-brca/README.md)** *(core: featured missions)* | A tumor sample with clinical, survival, mutation, copy number, RNA and protein data, plus slide links | ~70 MB | Cohort tools, release monitors, case workspaces, evidence assistants | **Ready** |
| **[Pathology: PathMNIST](pathmnist/README.md)** *(best first image experience)* | A labelled colorectal tissue patch | Smallest version by default (size confirmed at first download) | Tissue classification, visual search, image-quality checks, review queues | **Ready to test:** publisher checksums pinned; first real download pending |
| **[Molecular + imaging: CPTAC](cptac/README.md)** | A lung, colon or kidney cancer case | Slide and CT manifests: < 1 MB | Case workspaces linked to tissue; RNA vs protein (when added) | **Slides and CT ready; protein pending** |
| **[Imaging: LIDC-IDRI](lidc-idri/README.md)** | A chest CT with up to 4 radiologists' nodule marks | Optional 34 to 230 MB exercise | Compare model output with reviewer annotations | **Ready** |
| **[Prediction: DepMap](depmap/README.md)** | A cancer cell line | (planned) | Predict sensitivity to a gene knockout; explain failures | Planned |
| **[Trial records: ClinicalTrials.gov](clinical-trials/README.md)** | A dated version of a trial's eligibility rules + fictional cases | (planned) | Compare eligibility versions; who moves in or out | Planned |
| **[Advanced: CAMELYON17](camelyon17/README.md)** | A lymph-node whole-slide image from one of 5 hospitals | Labels only; slides source-linked | Test performance across hospitals | **Ready (source-linked)** |
| **[Warm-up: Wisconsin](../warmup/wisconsin/README.md)** | A breast-mass sample scored 1 to 10 on nine features | < 1 MB | A 30-minute tabular practice | **Ready** |

## The joining rule
These packs describe **different things**: tissue patches, cell lines, tumor samples, CT scans, trial records. **Only join records where a documented match exists**, such as TCGA barcodes within TCGA, or CPTAC case IDs with a verified mapping. Never join across packs because IDs or labels look similar. When a match is missing, show the gap: that's a finding, not a failure.

## How every pack is built
Each folder has the same pieces, so every source is documented and checkable the same way:
1. **`README.md`:** what one record means, how files connect, coverage, license, citation, and what the data can't support.
2. **`sources.csv`:** each file's URL, checksum, size, license and retrieval date.
3. **A fetch script** that downloads into `raw/` (not committed) and stops if a checksum doesn't match.
4. **Small manifests, committed:** tables that link the pieces (samples, images, versions), with viewer links where images stay at the source.

## Adding a pack
Make `data/<pack>/` with the four pieces above, and add `data/<pack>/raw/` to `.gitignore`.
- **Commit** only small files whose license clearly allows redistribution, such as CC0 or CC BY with attribution.
- **Fetch, don't commit,** anything large or where redistribution isn't confirmed.
- **Never** commit controlled-access data, non-commercial-licensed data, credentials, or personal identifiers.
