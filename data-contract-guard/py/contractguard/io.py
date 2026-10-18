"""Read a dataset from CSV, Parquet, JSON Lines or JSON, keeping values as written so type checks see the truth."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FORMATS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".parquet": "parquet",
    ".pq": "parquet",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".json": "json",
}


class DataError(ValueError):
    """The data file cannot be read."""


def read_data(path: str | Path, fmt: str | None = None) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise DataError(f"{p}: file not found")
    kind = fmt or FORMATS.get(p.suffix.lower())
    if kind is None:
        raise DataError(f"{p}: unknown file type '{p.suffix}' (use --data-format csv|tsv|parquet|jsonl|json)")
    try:
        if kind in ("csv", "tsv"):
            # read everything as text: a contract must catch "12a" in an integer column, not have pandas hide it
            return pd.read_csv(p, sep="\t" if kind == "tsv" else ",", dtype=str, keep_default_na=False, na_values=[""])
        if kind == "parquet":
            return pd.read_parquet(p)
        if kind == "jsonl":
            return pd.read_json(p, lines=True, dtype=False)
        if kind == "json":
            return pd.read_json(p, dtype=False)
    except Exception as error:
        raise DataError(f"{p}: could not read as {kind} ({type(error).__name__}: {error})") from error
    raise DataError(f"{p}: unsupported format '{kind}'")
