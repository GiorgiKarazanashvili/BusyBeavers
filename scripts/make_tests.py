import json, subprocess, sys
from pathlib import Path

P, M, C, R = "protein_rppa.tsv.gz", "mutation_gene_level.tsv.gz", "copy_number_gistic.tsv.gz", "rna_hiseq.tsv.gz"
ER, PAM = "breast_carcinoma_estrogen_receptor_status", "PAM50Call_RNAseq"

def swap(f, opp=False, n=1): return {"type": "swap_samples", "file": f, "count": n, "opposite_er": opp}
def dups(f, sub, n=5):       return {"type": "replace_with_duplicates", "file": f, "count": n, "subtype": sub}
def relabel(col, val, n=5):  return {"type": "relabel_clinical", "file": "clinical.tsv", "column": col, "new_value": val, "count": n}

TESTS = {
  "t0-no-change":             [],
  "t1-protein-swap-cross-er": [swap(P, True)],
  "t2-protein-swap-same-er":  [swap(P, False)],
  "t3-protein-dups-basal":    [dups(P, "Basal")],
  "t4-er-relabel":            [relabel(ER, "Negative")],
  "t5-subtype-relabel":       [relabel(PAM, "Basal")],
  "t6-copynumber-swap":       [swap(C, True)],
  "t7-unread-relabel":        [relabel("AJCC_Stage_nature2012", "Stage X")],   # neither A1 nor A2 reads this
  "t8-combined":              [swap(P, True), dups(P, "Her2"), relabel(PAM, "Basal", 3)],
  "t9-rna-dups-her2":         [dups(R, "Her2")],
  "t10-four-protein-swaps":   [swap(P, True, 4)],
  "t11-er-to-indeterminate":  [relabel(ER, "Indeterminate", 3)],
  "t12-mutation-dups-lumb":   [dups(M, "LumB", 3)],
}

cfgdir = Path("scratch/configs"); cfgdir.mkdir(parents=True, exist_ok=True)
for seed, (name, changes) in enumerate(TESTS.items(), start=100):
    p = cfgdir / f"{name}.json"
    p.write_text(json.dumps({"name": name, "seed": seed, "changes": changes}))
    subprocess.run([sys.executable, "data/tcga-brca/make_release.py", "--config", str(p)], check=True)