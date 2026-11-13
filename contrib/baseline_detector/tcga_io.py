"""Readers for TCGA-BRCA release files.

Two layouts exist:
  * row tables  (one row per sample): clinical.tsv (id column ``sampleID``), survival.tsv (``sample``)
  * matrices    (features x samples): mutation, protein, copy number, RNA (first column = feature)

Everything is read as exact text (dtype=str, keep_default_na=False) so profile hashes reflect
the file content byte-for-byte, the same convention data/tcga-brca/make_release.py uses.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROW_TABLES = {"clinical.tsv": "sampleID", "survival.tsv": "sample"}
MISSING_TOKENS = ("", "NA", "NaN", "nan", "null", "NULL", "None", "[Not Available]", "[Not Applicable]")


@dataclass
class Profiles:
    """Sample-keyed view of one file: a DataFrame indexed by feature, one column per sample id."""

    file: str
    layout: str  # "table" | "matrix"
    frame: pd.DataFrame  # index = feature/field name, columns = sample ids (str values)
    duplicate_ids: list[str]  # ids appearing more than once in the file (kept first)

    @property
    def ids(self) -> list[str]:
        return list(self.frame.columns)

    @property
    def features(self) -> list[str]:
        return list(self.frame.index)


def read_profiles(path: Path, file: str) -> Profiles:
    if file in ROW_TABLES:
        df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
        id_col = ROW_TABLES[file]
        if id_col not in df.columns:
            id_col = df.columns[0]
        ids = df[id_col].astype(str)
        dup = sorted(set(ids[ids.duplicated()]))
        df = df[~ids.duplicated()].set_index(id_col)
        frame = df.T  # fields x samples
        frame.columns = [str(c) for c in frame.columns]
        return Profiles(file=file, layout="table", frame=frame, duplicate_ids=dup)
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, index_col=0)
    cols = pd.Index([str(c) for c in df.columns])
    dup = sorted(set(cols[cols.duplicated()]))
    df.columns = cols
    df = df.loc[:, ~cols.duplicated()]
    df = df[~df.index.duplicated()]
    return Profiles(file=file, layout="matrix", frame=df, duplicate_ids=dup)


def patient_of(sample_id: str) -> str:
    return sample_id[:12]


def sample_type_code(sample_id: str) -> str:
    return sample_id[13:15]


def is_primary(sample_id: str) -> bool:
    return sample_type_code(sample_id) == "01"


def read_header_ids(path: Path, file: str) -> list[str]:
    """Cheap sample-id list (header only for matrices) used for release inventories."""
    if file in ROW_TABLES:
        df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, usecols=[0])
        return [str(x) for x in df.iloc[:, 0]]
    df = pd.read_csv(path, sep="\t", dtype=str, nrows=0, index_col=0)
    return [str(c) for c in df.columns]
