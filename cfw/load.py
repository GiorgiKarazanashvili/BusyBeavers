import re
from pathlib import Path
import pandas as pd

BARCODE = re.compile(r"^TCGA-\w\w-\w{4}-\d\d")

def _samples_as_rows(df):
    """Detect orientation by looking for TCGA barcodes, not by filename."""
    if df.index.astype(str).str.match(BARCODE).mean() > 0.5:
        return df
    if pd.Index(df.columns).astype(str).str.match(BARCODE).mean() > 0.5:
        return df.T
    raise ValueError("no TCGA barcodes found on either axis")

def load_release(path):
    out = {}
    for f in sorted(Path(path).glob("*.tsv*")):
        df = pd.read_csv(f, sep="\t", index_col=0, low_memory=False)
        df = _samples_as_rows(df)
        df.columns = df.columns.astype(str)              # NaN -> "nan", everything is a str now
        dup = df.columns.duplicated()
        if dup.any():
            print(f"[load] {f.name}: dropping {dup.sum()} duplicate feature name(s)")
            df = df.loc[:, ~dup]
        out[f.name.split(".")[0]] = df
    return out