import re
from pathlib import Path
import pandas as pd

BARCODE = re.compile(r"^TCGA-\w\w-\w{4}-\d\d")

def _samples_as_rows(df):
    if df.index.astype(str).str.match(BARCODE).mean() > 0.5:
        return df
    if pd.Index(df.columns).astype(str).str.match(BARCODE).mean() > 0.5:
        return df.T
    raise ValueError("no TCGA barcodes found on either axis")

def load_release(path, only=None):
    """Load a release. only = optional set of file stems (e.g. {'clinical'}) to restrict loading."""
    out = {}
    for f in sorted(Path(path).glob("*.tsv*")):
        if only is not None and f.name.split(".")[0] not in only:
            continue
        df = pd.read_csv(f, sep="\t", index_col=0, low_memory=False)
        df = _samples_as_rows(df)
        df.columns = df.columns.astype(str)
        dup = df.columns.duplicated()
        if dup.any():
            df = df.loc[:, ~dup]
        out[f.name.split(".")[0]] = df
    return out