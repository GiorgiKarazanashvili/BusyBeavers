import numpy as np
import pandas as pd

def profile_hashes(df):
    d = df.reindex(sorted(df.columns, key=str), axis=1).round(4)
    h = pd.util.hash_pandas_object(d, index=False)
    h.index = df.index
    return h[~d.isna().all(axis=1)]


def rows_close(ra, rb, rtol=1e-6, atol=1e-9):
    """True if two sample rows hold the same values up to float noise (text must match exactly).

    Hash-after-rounding can flip on values sitting exactly on a rounding boundary, so whenever two
    hashes differ we confirm with this tolerance check before reporting a change.
    """
    cols = ra.index.intersection(rb.index)
    x, y = ra[cols], rb[cols]
    xn, yn = pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")
    num = xn.notna() & yn.notna()
    if not np.isclose(xn[num].astype(float), yn[num].astype(float), rtol=rtol, atol=atol).all():
        return False
    rest = ~num
    return bool((((x[rest] == y[rest]) | (x[rest].isna() & y[rest].isna()))).all())