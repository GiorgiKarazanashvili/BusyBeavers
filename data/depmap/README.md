# Prediction pack: Broad DepMap (planned)

**One record = one cancer cell line grown in a lab**, with gene expression and CRISPR dependency scores: how much the cell line's growth depends on each gene.

**Status: planned, not yet available.** The organizers couldn't reach DepMap from the environment used to build this pack, so its current license and file sizes haven't been checked.

## What it will contain
- A frozen extract: selected gene expression and CRISPR dependency values for a documented set of cell lines, with `sources.csv` checksums and the DepMap release name.
- A documented split that keeps related cell lines (same lineage) on the same side.
- A simple baseline and its predictions.

## The exercise
Predict which cell lines are sensitive to knocking out a particular gene, then build a tool that explains where the model fails.

**This is a lab prediction, not a patient treatment prediction.** A cell line's response says nothing by itself about a patient.

## What it can't do
Cell lines aren't patients: **don't join DepMap to TCGA, CPTAC or any patient record.**

## To make it ready (organizers)
1. Confirm the DepMap release and its license terms on depmap.org.
2. Pick 1 target gene, the expression features, and about 500 to 1,000 cell lines. Keep the download under about 200 MB.
3. Build the split by lineage, run the baseline, and pin checksums in `sources.csv`.
