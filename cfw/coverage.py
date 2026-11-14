"""Coverage lost by subgroup: how many primary tumors each data file holds per clinical subgroup, A vs B.

A release can keep its total sample count while one subgroup quietly shrinks (e.g. 5 Her2 samples replaced
by copies of LumA samples). Subgroup labels come from release A's clinical file (falling back to B's for
ids A does not have), so the comparison isolates which samples a data file contains.
"""
import pandas as pd

SUBGROUPS = {"PAM50 subtype": "PAM50Call_RNAseq",
             "ER status": "breast_carcinoma_estrogen_receptor_status"}


def _primary(ids):
    return {i for i in ids if str(i)[13:15] == "01"}


def _labels(A, B, col):
    parts = []
    for rel in (A, B):                                   # A first: its labels win
        if "clinical" in rel and col in rel["clinical"].columns:
            s = rel["clinical"][col]
            parts.append(s[~s.index.duplicated()])
    if not parts:
        return pd.Series(dtype=object)
    out = parts[0]
    for p in parts[1:]:
        out = out.combine_first(p)
    return out.dropna()


def coverage_loss(A, B):
    out = []
    for stem in sorted(set(A) & set(B) - {"clinical"}):
        ia, ib = _primary(A[stem].index), _primary(B[stem].index)
        for name, col in SUBGROUPS.items():
            lab = _labels(A, B, col)
            for value in sorted(lab.unique()):
                if value == "":
                    continue
                sa = {i for i in ia if lab.get(i) == value}
                sb = {i for i in ib if lab.get(i) == value}
                if len(sb) < len(sa):
                    out.append(dict(type="coverage_loss", file=stem, subgroup=f"{name}={value}",
                                    before=len(sa), after=len(sb), total_before=len(ia), total_after=len(ib),
                                    sample_ids=sorted(sa - sb)))
    return out