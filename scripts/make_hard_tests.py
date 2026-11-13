"""Plant harder changes than make_release.py supports, and write a CHANGES.json answer key for each.

Run from the repo root:   python scripts/make_hard_tests.py
Builds data/tcga-brca/releases/t13-... t21-...  (no RNA file, like the sealed envelopes).
Unchanged files are hard-linked, so each test costs almost no disk.
"""
import json, os, random, shutil
from pathlib import Path
import pandas as pd

RAW = Path(os.environ.get("CFW_RAW", "data/tcga-brca/raw"))
OUT = Path(os.environ.get("CFW_OUT", "data/tcga-brca/releases"))
ER, PAM = "breast_carcinoma_estrogen_receptor_status", "PAM50Call_RNAseq"
CLIN, PROT = "clinical.tsv", "protein_rppa.tsv.gz"

def read_clin():
    return pd.read_csv(RAW / CLIN, sep="\t", dtype=str, keep_default_na=False)
def read_prot():
    return pd.read_csv(RAW / PROT, sep="\t", index_col=0, dtype=str, keep_default_na=False)
def write(df, dest, name):
    if name == CLIN:
        df.to_csv(dest / name, sep="\t", index=False)
    else:
        df.to_csv(dest / name, sep="\t", compression={"method": "gzip", "mtime": 0})

def prim(ids): return [i for i in ids if str(i)[13:15] == "01"]
def num(v):
    try: return float(v)
    except ValueError: return None

class S:                                   # mutable state for one release
    def __init__(self, seed):
        self.rng, self.used, self.log, self.touched = random.Random(seed), set(), [], set()
        self.clin, self.prot = read_clin(), read_prot()
    def er(self): return self.clin.set_index("sampleID")[ER]
    def pam(self): return self.clin.set_index("sampleID")[PAM]
    def pick(self, pool, n):
        pool = sorted(p for p in pool if p not in self.used)
        got = self.rng.sample(pool, n); self.used |= set(got); return got

def clinical_swap(s):
    er, pam = s.er(), s.pam()
    cols = [c for c in prim(s.prot.columns) if er.get(c) in ("Positive", "Negative") and pam.get(c)]
    while True:
        a, b = s.rng.sample(sorted(c for c in cols if c not in s.used), 2)
        if er[a] != er[b] and pam[a] != pam[b]: break
    s.used |= {a, b}
    keep = [c for c in s.clin.columns if c != "sampleID"]
    ia, ib = s.clin.index[s.clin.sampleID == a][0], s.clin.index[s.clin.sampleID == b][0]
    ra, rb = s.clin.loc[ia, keep].copy(), s.clin.loc[ib, keep].copy()
    s.clin.loc[ia, keep], s.clin.loc[ib, keep] = rb.values, ra.values
    s.touched.add(CLIN)
    s.log.append({"type": "swap_clinical_rows", "file": CLIN, "samples": [a, b],
                  "note": "the two samples exchanged all clinical fields (ER and subtype differ)"})

def eralpha_blank(s, n=8):
    er = s.er()
    ids = s.pick([c for c in prim(s.prot.columns) if er.get(c) == "Positive"], n)
    s.prot.loc["ERALPHA", ids] = ""
    s.touched.add(PROT)
    s.log.append({"type": "blank_value", "file": PROT, "samples": ids, "feature": "ERALPHA"})

def protein_sparse(s, n=6, frac=0.3):
    pam = s.pam()
    ids = s.pick([c for c in prim(s.prot.columns) if pam.get(c) == "Basal"], n)
    for c in ids:
        rows = s.rng.sample(list(s.prot.index), int(len(s.prot.index) * frac))
        s.prot.loc[rows, c] = ""
    s.touched.add(PROT)
    s.log.append({"type": "blank_many_values", "file": PROT, "samples": ids, "fraction": frac})

def protein_other_gene(s, n=3):
    ids = s.pick(prim(s.prot.columns), n)
    rows = [r for r in s.prot.index if r != "ERALPHA"]
    for c in ids:
        r = next(x for x in s.rng.sample(rows, len(rows)) if num(s.prot.at[x, c]) is not None)
        s.prot.at[r, c] = f"{num(s.prot.at[r, c]) + 0.5:.6g}"
    s.touched.add(PROT)
    s.log.append({"type": "edit_other_feature", "file": PROT, "samples": ids,
                  "note": "a protein other than ERALPHA changed: file changes, A1 and A2 must be left alone"})

def clinical_dup(s, n=2):
    pam = s.pam()
    src = s.pick([c for c in prim(s.clin.sampleID) if pam.get(c)], n)
    new = [f"TCGA-ZZ-{9000 + k}-01" for k in range(n)]
    rows = s.clin[s.clin.sampleID.isin(src)].copy().set_index("sampleID").loc[src].reset_index()
    rows["sampleID"] = new
    s.clin = pd.concat([s.clin, rows], ignore_index=True)
    s.touched.add(CLIN)
    s.log.append({"type": "clinical_duplicates_under_new_id", "file": CLIN,
                  "samples": new + src, "duplicates": [{"new_id": a, "copied_from": b} for a, b in zip(new, src)]})

def clinical_remove(s, n=3):
    er = s.er()
    ids = s.pick([c for c in prim(s.prot.columns) if er.get(c) in ("Positive", "Negative")], n)
    s.clin = s.clin[~s.clin.sampleID.isin(ids)].reset_index(drop=True)
    s.touched.add(CLIN)
    s.log.append({"type": "clinical_rows_removed", "file": CLIN, "samples": ids,
                  "note": "still present in protein_rppa"})

def id_drift(s):
    ids = s.pick(prim(s.prot.columns), 5)
    ren = {c: (c.lower() if k < 3 else c + " ") for k, c in enumerate(ids)}
    s.prot = s.prot.rename(columns=ren)
    s.touched.add(PROT)
    s.log.append({"type": "id_format_drift", "file": PROT, "samples": ids,
                  "note": "3 ids lower-cased, 2 with a trailing space. Not a real sample change; a tool should say so"})

def noise_reorder(s):
    cols = list(s.prot.columns); s.rng.shuffle(cols)
    rows = list(s.prot.index); s.rng.shuffle(rows)
    p = s.prot.loc[rows, cols].copy()
    for c in p.columns:
        p[c] = [repr(num(v) * (1 + 1e-12)) if num(v) is not None else v for v in p[c]]
    s.prot = p
    s.clin = s.clin.sample(frac=1, random_state=1).reset_index(drop=True)
    s.touched |= {CLIN, PROT}
    s.log.append({"type": "reorder_and_float_noise", "file": f"{CLIN}, {PROT}", "samples": [],
                  "note": "rows/columns shuffled, values perturbed by 1e-12: NOT a change"})

TESTS = {
    "t13-clinical-row-swap":      [clinical_swap],
    "t14-eralpha-blanked":        [eralpha_blank],
    "t15-protein-sparse-basal":   [protein_sparse],
    "t16-protein-other-gene":     [protein_other_gene],
    "t17-clinical-dup-new-id":    [clinical_dup],
    "t18-clinical-rows-removed":  [clinical_remove],
    "t19-id-format-drift":        [id_drift],
    "t20-reorder-noise":          [noise_reorder],
    "t21-combined-hard":          [clinical_swap, eralpha_blank, clinical_remove, clinical_dup, protein_other_gene],
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for seed, (name, ops) in enumerate(TESTS.items(), start=200):
        dest = OUT / name
        if (dest / "CHANGES.json").exists():
            continue
        if dest.exists(): shutil.rmtree(dest)
        dest.mkdir(parents=True)
        s = S(seed)
        for op in ops: op(s)
        for f in RAW.iterdir():
            if f.name.startswith("rna_hiseq"): continue            # envelopes ship without RNA
            if f.name == CLIN and CLIN in s.touched: write(s.clin, dest, CLIN)
            elif f.name == PROT and PROT in s.touched: write(s.prot, dest, PROT)
            else:
                try: os.link(f, dest / f.name)
                except OSError: shutil.copy(f, dest / f.name)
        json.dump({"release": name, "based_on": "raw", "changes": s.log}, open(dest / "CHANGES.json", "w"), indent=2)
        print("built", name, [c["type"] for c in s.log])