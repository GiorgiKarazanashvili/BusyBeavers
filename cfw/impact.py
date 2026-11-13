import pandas as pd
from .fingerprint import profile_hashes, rows_close

ER = "breast_carcinoma_estrogen_receptor_status"
def _primary(ids): return [i for i in ids if str(i)[13:15] == "01"]

def slice_a1(rel):
    if "clinical" not in rel or "protein_rppa" not in rel: return None
    er, pr = rel["clinical"][ER], rel["protein_rppa"]["ERALPHA"]
    ids = [s for s in _primary(pr.index) if er.get(s) in ("Positive", "Negative")]
    return pd.DataFrame({"er": er.loc[ids], "eralpha": pr.loc[ids]})

def slice_a2(rel):
    if "clinical" not in rel: return None
    c = rel["clinical"]["PAM50Call_RNAseq"]
    return c[_primary(c.index)].dropna().to_frame()

ANALYSES = {
    "A1": dict(slice=slice_a1, reads="clinical[%s] + protein[ERALPHA], primary tumors with Positive/Negative ER" % ER),
    "A2": dict(slice=slice_a2, reads="clinical[PAM50Call_RNAseq], primary tumors"),
}

def impact(A, B):
    res = {}
    for k, spec in ANALYSES.items():
        sa, sb = spec["slice"](A), spec["slice"](B)
        if sa is None or sb is None:
            res[k] = dict(affected=True, reason="input file missing in one release", sample_ids=[]); continue
        ha, hb = profile_hashes(sa), profile_hashes(sb)
        sa_ids, sb_ids = set(ha.index), set(hb.index)
        ids = sorted((sa_ids ^ sb_ids) | {i for i in sa_ids & sb_ids if ha[i] != hb[i] and not rows_close(sa.loc[i], sb.loc[i])})
        res[k] = dict(affected=bool(ids), sample_ids=ids,
                      reason=(f"{len(ids)} sample(s) changed inside the slice it reads ({spec['reads']})" if ids else
                              f"slice it reads is identical after rounding across {len(ha)} samples ({spec['reads']})"))
    return res