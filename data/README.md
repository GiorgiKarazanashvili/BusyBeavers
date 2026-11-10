# Data

Each dataset lives in its own folder with the same five pieces, so every source is documented, reproducible and checkable the same way.

| Folder | Dataset | Status |
|---|---|---|
| [`tcga-brca/`](tcga-brca/README.md) | TCGA breast cancer: clinical, survival, mutations, copy number, RNA, protein, pathology slides | Ready |
| [`../warmup/wisconsin/`](../warmup/wisconsin/README.md) | Breast Cancer Wisconsin (Original): a 30-minute warm-up exercise | Ready |

## How to add a dataset
1. **Make a folder:** `data/<dataset-name>/`.
2. **`README.md`:** what one row means, how the files connect, coverage numbers, license, citation, and what the data can't support.
3. **`sources.csv`:** one row per file with `file, layer, source_url, sha256, bytes, license, retrieved`. Fill `sha256` from a download you checked yourself.
4. **`fetch.py`:** downloads each file into `data/<dataset-name>/raw/` and stops if a checksum doesn't match. Copy `tcga-brca/fetch.py`; it only reads `sources.csv`. Add `data/<dataset-name>/raw/` to `.gitignore`.
5. **Small manifests, committed:** tables that link the pieces together (samples, images, versions), under a few MB each. Generate them with a script and record how.

## Rules for what goes in the repository
- **Commit** only files that are small (under about 50 MB) **and** whose license clearly allows redistribution, such as CC0 or CC BY with attribution.
- **Fetch, don't commit,** anything large or where redistribution isn't confirmed. Pin its checksum in `sources.csv`.
- **Never** commit controlled-access data, non-commercial-licensed data, credentials, or anything with personal identifiers.
- **Images** stay in the cloud: link to a viewer, or list them in a manifest that `idc-index` can download.
