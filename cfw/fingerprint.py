import pandas as pd

def profile_hashes(df):
    d = df.reindex(sorted(df.columns, key=str), axis=1).round(4)
    h = pd.util.hash_pandas_object(d, index=False)
    h.index = df.index
    return h[~d.isna().all(axis=1)]