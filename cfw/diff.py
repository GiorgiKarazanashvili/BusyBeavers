import pandas as pd
from .fingerprint import profile_hashes

def _dup_groups(h):
    d = h[h.duplicated(keep=False)]
    return {frozenset(g.index) for _, g in d.groupby(d)}

def diff_file(name, a_df, b_df):
    a, b = profile_hashes(a_df), profile_hashes(b_df)
    out = []
    added, removed = b.index.difference(a.index), a.index.difference(b.index)
    if len(added):   out.append(dict(type="samples_added", file=name, sample_ids=sorted(added)))
    if len(removed): out.append(dict(type="samples_removed", file=name, sample_ids=sorted(removed)))
    if b.index.duplicated().any():
        out.append(dict(type="duplicate_id", file=name, sample_ids=sorted(set(b.index[b.index.duplicated()]))))
    a, b = a[~a.index.duplicated()], b[~b.index.duplicated()]

    common = a.index.intersection(b.index)
    changed = [i for i in common if a[i] != b[i]]
    a_by_hash = a.groupby(a).groups
    seen = set()
    for i in changed:                                    # swaps: i now holds j's old profile
        for j in a_by_hash.get(b[i], []):
            if j != i and j in b.index and b[j] == a[i] and frozenset((i, j)) not in seen:
                seen.add(frozenset((i, j)))
                out.append(dict(type="swap", file=name, sample_ids=sorted([i, j])))
    swapped = set().union(*seen) if seen else set()
    for i in changed:
        if i in swapped: continue
        cols = [c for c in a_df.columns.intersection(b_df.columns)
                if not (pd.isna(a_df.at[i, c]) and pd.isna(b_df.at[i, c])) and a_df.at[i, c] != b_df.at[i, c]]
        out.append(dict(type="profile_modified", file=name, sample_ids=[i], columns_changed=cols[:10]))

    for g in _dup_groups(b) - _dup_groups(a):            # only NEW duplicate groups
        out.append(dict(type="duplicate_profile", file=name, sample_ids=sorted(g)))

    na_a, na_b = a_df.isna().mean(axis=1), b_df.isna().mean(axis=1)
    worse = [i for i in common if na_b.get(i, 0) - na_a.get(i, 0) > 0.05]
    if worse: out.append(dict(type="missingness_increased", file=name, sample_ids=sorted(worse)))
    return out

def diff_releases(A, B):
    findings = []
    for name in sorted(set(A) | set(B)):
        if name not in B: findings.append(dict(type="file_removed", file=name, sample_ids=[]))
        elif name not in A: findings.append(dict(type="file_added", file=name, sample_ids=[]))
        else: findings += diff_file(name, A[name], B[name])
    return findings