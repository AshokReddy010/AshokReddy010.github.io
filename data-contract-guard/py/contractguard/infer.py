"""Draft a contract from a sample of data, so a team starts from what the data looks like today.

The draft is deliberately conservative: it records what is true of the sample (types, which columns are never
blank, which are unique, small sets of categories, numeric ranges) and leaves the judgement calls to a human
reviewer. Every inferred bound is something to read before committing, not a promise.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .checks import as_text, coerce, is_present
from .contract import Column, Contract

MAX_CATEGORIES = 12


def infer_type(s: pd.Series) -> str:
    v = s[is_present(s)]
    if v.empty:
        return "string"
    if pd.api.types.is_bool_dtype(v):
        return "boolean"
    if pd.api.types.is_integer_dtype(v):
        return "integer"
    if pd.api.types.is_float_dtype(v):
        return "integer" if bool((v % 1 == 0).all()) else "float"
    if pd.api.types.is_datetime64_any_dtype(v):
        return "timestamp"
    for typ in ("boolean", "integer", "float"):
        if not coerce(v, typ)[1].any():
            if typ == "boolean" and set(as_text(v).str.lower()) <= {"0", "1"}:
                continue  # 0/1 columns are more often counts or flags kept as integers
            return typ
    text = as_text(v)
    if text.str.match(r"^\d{4}-\d{2}-\d{2}").all():
        d, bad = coerce(v, "date")
        if not bad.any():
            return "date"
        if not coerce(v, "timestamp")[1].any():
            return "timestamp"
    return "string"


def infer_contract(df: pd.DataFrame, dataset: str = "dataset", owner: str | None = None) -> Contract:
    cols: list[Column] = []
    pk: tuple[str, ...] = ()
    for name in df.columns:
        s = df[name]
        typ = infer_type(s)
        present = is_present(s)
        values = s[present]
        unique = bool(len(values) > 1 and values.is_unique and len(values) == len(s))
        kw: dict[str, Any] = {"name": str(name), "type": typ, "nullable": bool(not present.all()), "unique": unique}
        if typ in ("integer", "float") and len(values):
            num = pd.to_numeric(values, errors="coerce")
            if float(num.min()) >= 0:
                kw["min"] = 0  # sign is a safer promise than the sample's exact minimum
            if typ == "integer":
                kw["min"] = int(kw["min"]) if "min" in kw else None
        elif typ == "string" and len(values):
            distinct = as_text(values).unique()
            if not unique and 1 < len(distinct) <= MAX_CATEGORIES and len(values) >= 3 * len(distinct):
                kw["allowed"] = tuple(sorted(distinct))
            lengths = as_text(values).str.len()
            if lengths.min() == lengths.max() and len(values) > 1:
                shape = _shape(as_text(values))
                if shape:
                    kw["pattern"] = shape
            kw["max_length"] = int(lengths.max())
        cols.append(Column(**{k: v for k, v in kw.items() if v is not None}))
        if unique and not pk and typ in ("string", "integer") and str(name).lower().endswith("id"):
            pk = (str(name),)
    return Contract(dataset=dataset, version="0.1.0", owner=owner, columns=tuple(cols), row_count_min=1, primary_key=pk)


def _shape(values: pd.Series) -> str | None:
    """A regular expression for fixed-width codes like ORD-000123, if every value shares the same shape."""

    def one(v: str) -> str:
        out, prev, n = [], "", 0
        for ch in v:
            k = r"[0-9]" if ch.isdigit() else r"[A-Z]" if ch.isupper() else r"[a-z]" if ch.islower() else re.escape(ch)
            if k == prev:
                n += 1
            else:
                if prev:
                    out.append(prev + (f"{{{n}}}" if n > 1 else ""))
                prev, n = k, 1
        if prev:
            out.append(prev + (f"{{{n}}}" if n > 1 else ""))
        return "^" + "".join(out) + "$"

    shapes = values.map(one).unique()
    return str(shapes[0]) if len(shapes) == 1 else None
