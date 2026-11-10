# Pathology pack: PathMNIST

**One record = one small image patch of colorectal tissue, labelled with one of nine tissue types.** It's the quickest way to start building with images: the default download is the smallest version, it runs on a laptop, and no GPU is needed.

## Get started
```bash
python data/pathmnist/fetch.py
```
```bash
python data/pathmnist/gallery.py
```
```bash
python data/pathmnist/baseline.py
```
1. **`fetch.py`** downloads the 28 × 28-pixel version (the smallest) and checks it against the publisher's MD5 checksum. Add `--size 64`, `128` or `224` for sharper, larger versions; 64 or more is better for blur and color tests. Use the same `--size` with the other two scripts.
2. **`gallery.py`** builds `gallery/index.html`, a page you can browse with 24 test patches per tissue type and the plain-English guide below.
3. **`baseline.py`** trains a simple CPU model in a few minutes and writes **sample AI outputs** to `outputs/`:
   - `test_predictions.csv`: true label, predicted label, a probability for each class, and confidence
   - `review_queue.csv`: the 200 least confident predictions

   Use them if you'd rather build the review or search experience than train a model.

Requires `pip install numpy pillow scikit-learn pandas`.

## Label guide
| # | Label | What it looks like |
|---|---|---|
| 0 | adipose | Fat tissue: large, empty-looking cells |
| 1 | background | No tissue: glass or empty slide |
| 2 | debris | Dead cells and fragments |
| 3 | lymphocytes | Immune cells: small, dark, round nuclei |
| 4 | mucus | Pale, wispy material |
| 5 | smooth muscle | Long pink fibers |
| 6 | normal colon mucosa | Healthy lining of the colon |
| 7 | cancer-associated stroma | Supporting tissue around a tumor |
| 8 | colorectal adenocarcinoma epithelium | Tumor cells from the colon lining |

These are **tissue types, not diagnoses**. A model that labels a patch "tumor epithelium" is a research output.

## Splits
| Split | Patches | Source |
|---|---|---|
| train | 89,996 | NCT-CRC-HE-100K (86 slides) |
| val | 10,004 | NCT-CRC-HE-100K |
| test | 7,180 | CRC-VAL-HE-7K: **50 different patients**, so the test set measures how a model holds up on new patients |

## What it opens up
Tissue classifiers, visual search ("find patches like this one"), image-quality checks (blur, color shift), and review queues for uncertain predictions. Missions: Model Crash Lab, Pathology Search and Review.

## What it can't do
The patches have no patient IDs, clinical data or molecular data, so **don't join them to TCGA or CPTAC records**. There's no documented match.

## Status and source
- **Status:** checksums are pinned from the official `medmnist` package (see `sources.csv`). File sizes will be added after the first real download. The organizers couldn't download from Zenodo in the environment used to build this pack, so the fetch and the baseline's accuracy on real data still need a run on a normal laptop before kickoff. The gallery and baseline code were tested on a stand-in file with the same structure.
- **Source:** Yang, J. et al. MedMNIST v2: A large-scale lightweight benchmark for 2D and 3D biomedical image classification. *Scientific Data* 10, 41 (2023). Original images: Kather, J.N., Halama, N. & Marx, A. 100,000 histological images of human colorectal cancer and healthy tissue (Zenodo, 2018).
- **License:** CC BY 4.0.
