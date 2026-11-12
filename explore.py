import pandas as pd
from pathlib import Path

ROOT = Path("data/tcga-brca")
FILES = ["clinical.tsv", "survival.tsv", "mutation_gene_level.tsv.gz",
         "protein_rppa.tsv.gz", "copy_number_gistic.tsv.gz", "rna_hiseq.tsv.gz"]

for label, d in [("A", ROOT / "raw"), ("B", ROOT / "releases/practice-B")]:
    print(f"\n===== Release {label} =====")
    for f in FILES:
        p = d / f
        if not p.exists():
            print(f"{f}: MISSING"); continue
        df = pd.read_csv(p, sep="\t", index_col=0, low_memory=False)
        print(f"{f}: shape={df.shape}")
        print("   index[:3]  :", list(df.index[:3]))
        print("   columns[:3]:", list(df.columns[:3]))