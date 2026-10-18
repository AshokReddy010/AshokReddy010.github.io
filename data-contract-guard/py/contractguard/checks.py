"""Run a contract against a DataFrame and report every broken promise, with sample rows.

Each check returns a CheckResult. A check is "failed" when at least one row breaks it; the number of failing
rows and up to five example values are kept so the report says exactly what is wrong, not just that
something is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .contract import Column, Contract

SAMPLE = 5


@dataclass
class CheckResult:
    check: str  # e.g. "not_null", "type", "row_count"
    target: str  # column name, rule name or "dataset"
    severity: str  # "error" | "warn"
    passed: bool
    failing_rows: int = 0
    message: str = ""
    examples: list[Any] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "pass" if self.passed else ("fail" if self.severity == "error" else "warn")


@dataclass
class ValidationReport:
    dataset: str
    contract_version: str
    rows: int
    results: list[CheckResult]
    source: str | None = None

    @property
    def errors(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == "fail"]

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == "warn"]

    @property
    def ok(self) -> bool:
        return not self.errors


def validate(
    df: pd.DataFrame, contract: Contract, as_of: datetime | None = None, source: str | None = None
) -> ValidationReport:
    """Every check in the contract, in a stable order: dataset shape, then each column, then the rules."""
    results: list[CheckResult] = []
    results += _dataset_checks(df, contract, as_of or datetime.now(timezone.utc))
    for col in contract.columns:
        results += _column_checks(df, col)
    for rule in contract.rules:
        results.append(_rule_check(df, rule.name, rule.expr, rule.severity))
    return ValidationReport(
        dataset=contract.dataset, contract_version=contract.version, rows=len(df), results=results, source=source
    )


# ---------------------------------------------------------------- dataset level
def _dataset_checks(df: pd.DataFrame, c: Contract, as_of: datetime) -> list[CheckResult]:
    out: list[CheckResult] = []
    n = len(df)
    if c.row_count_min is not None or c.row_count_max is not None:
        ok = (c.row_count_min is None or n >= c.row_count_min) and (c.row_count_max is None or n <= c.row_count_max)
        out.append(
            CheckResult(
                "row_count",
                "dataset",
                "error",
                ok,
                0 if ok else n,
                f"{n:,} rows (expected {_range_text(c.row_count_min, c.row_count_max)})",
            )
        )
    missing = [col.name for col in c.columns if col.required and col.name not in df.columns]
    out.append(
        CheckResult(
            "required_columns",
            "dataset",
            "error",
            not missing,
            len(missing),
            "all required columns present" if not missing else f"missing: {', '.join(missing)}",
            missing[:SAMPLE],
        )
    )
    if not c.allow_extra_columns:
        extra = [x for x in df.columns if c.column(str(x)) is None]
        out.append(
            CheckResult(
                "no_extra_columns",
                "dataset",
                "error",
                not extra,
                len(extra),
                "no unexpected columns" if not extra else f"unexpected: {', '.join(map(str, extra))}",
                [str(x) for x in extra[:SAMPLE]],
            )
        )
    if c.primary_key and all(k in df.columns for k in c.primary_key):
        key = df[list(c.primary_key)]
        dup = key.duplicated(keep=False) & key.notna().all(axis=1)
        nulls = key.isna().any(axis=1)
        bad = int(dup.sum() + nulls.sum())
        ex = [" | ".join(str(v) for v in row) for row in key[dup | nulls].head(SAMPLE).itertuples(index=False)]
        out.append(
            CheckResult(
                "primary_key",
                "dataset",
                "error",
                bad == 0,
                bad,
                f"key ({', '.join(c.primary_key)}) is unique and complete"
                if bad == 0
                else f"{int(dup.sum()):,} rows share a key, {int(nulls.sum()):,} have a blank key part",
                ex,
            )
        )
    if c.freshness_column and c.freshness_column in df.columns:
        ts = pd.to_datetime(df[c.freshness_column], errors="coerce", utc=True)
        newest = ts.max()
        if pd.isna(newest):
            out.append(
                CheckResult("freshness", c.freshness_column, "error", False, n, "no valid dates to judge freshness")
            )
        else:
            age = (
                pd.Timestamp(as_of).tz_convert("UTC") if pd.Timestamp(as_of).tzinfo else pd.Timestamp(as_of, tz="UTC")
            ) - newest
            days = age.total_seconds() / 86400
            ok = days <= float(c.freshness_max_age_days or 0)
            out.append(
                CheckResult(
                    "freshness",
                    c.freshness_column,
                    "error",
                    ok,
                    0 if ok else n,
                    f"newest value {newest:%Y-%m-%d %H:%M} UTC is {days:.1f} days old "
                    f"(limit {c.freshness_max_age_days} days)",
                )
            )
    return out


# ---------------------------------------------------------------- column level
def _column_checks(df: pd.DataFrame, col: Column) -> list[CheckResult]:
    if col.name not in df.columns:
        return []  # reported once by required_columns
    s = df[col.name]
    sev = col.severity
    out: list[CheckResult] = []
    present = is_present(s)
    text = as_text(s)
    if not col.nullable:
        bad = ~present
        rows = pd.Series([f"row {i + 2}" for i in range(len(s))], index=s.index)  # +2: header line, 1-based
        out.append(_result("not_null", col.name, sev, bad, rows, "no blank values", "blank values"))
    typed, bad_type = coerce(s, col.type)
    bad_type = bad_type & present
    out.append(
        _result("type", col.name, sev, bad_type, s, f"all values are {col.type}", f"values that are not {col.type}")
    )
    ok_vals = typed[present & ~bad_type]
    if col.unique:
        dup = ok_vals.duplicated(keep=False)
        out.append(
            _result(
                "unique",
                col.name,
                sev,
                dup.reindex(s.index, fill_value=False),
                s,
                "values are unique",
                "duplicated values",
            )
        )
    if col.min is not None or col.max is not None:
        lo = _bound(col.min, col.type)
        hi = _bound(col.max, col.type)
        bad = pd.Series(False, index=s.index)
        if lo is not None:
            bad |= (ok_vals < lo).reindex(s.index, fill_value=False)
        if hi is not None:
            bad |= (ok_vals > hi).reindex(s.index, fill_value=False)
        out.append(
            _result(
                "range",
                col.name,
                sev,
                bad,
                s,
                f"within {_range_text(col.min, col.max)}",
                f"values outside {_range_text(col.min, col.max)}",
            )
        )
    if col.allowed is not None:
        allowed = {str(a) for a in col.allowed}
        bad = present & ~text.isin(allowed)
        out.append(
            _result(
                "allowed_values",
                col.name,
                sev,
                bad,
                s,
                f"all values in {sorted(allowed)}",
                "values not in the allowed list",
            )
        )
    if col.pattern is not None:
        rx = re.compile(col.pattern)
        bad = present & ~text.map(lambda v: bool(rx.fullmatch(v))).astype(bool)
        out.append(
            _result(
                "pattern",
                col.name,
                sev,
                bad,
                s,
                f"all values match {col.pattern}",
                f"values not matching {col.pattern}",
            )
        )
    if col.min_length is not None or col.max_length is not None:
        ln = text.map(len)
        bad = pd.Series(False, index=s.index)
        if col.min_length is not None:
            bad |= present & (ln < col.min_length)
        if col.max_length is not None:
            bad |= present & (ln > col.max_length)
        out.append(
            _result(
                "length",
                col.name,
                sev,
                bad,
                s,
                f"length within {_range_text(col.min_length, col.max_length)}",
                "values with the wrong length",
            )
        )
    return out


def _rule_check(df: pd.DataFrame, name: str, expr: str, severity: str) -> CheckResult:
    """A row-level rule written as a pandas expression. Rows where it is False fail; rows where a column the
    rule uses is blank or unreadable are skipped (the column's own checks already report those)."""
    used = [c for c in df.columns if re.search(rf"(?<![\w`]){re.escape(str(c))}(?![\w`])", expr)]
    parsed = df.copy()
    for c in used:  # compare dates as dates and numbers as numbers, not as text
        if parsed[c].dtype == object or pd.api.types.is_string_dtype(parsed[c]):
            filled = is_present(parsed[c])
            num = pd.to_numeric(parsed[c], errors="coerce")
            date = pd.to_datetime(parsed[c], errors="coerce", format="mixed")
            if filled.sum() and num[filled].notna().mean() >= 0.9:
                parsed[c] = num
            elif filled.sum() and date[filled].notna().mean() >= 0.9:
                parsed[c] = date
    try:
        ok = pd.Series(parsed.eval(expr, engine="python"), index=df.index)
    except Exception as error:  # a rule that cannot run is itself a failure
        return CheckResult("rule", name, severity, False, len(df), f"could not evaluate '{expr}': {error}")
    skip = pd.Series(False, index=df.index)
    for c in used:
        skip |= parsed[c].isna() | ~is_present(df[c])
    bad = ok.eq(False) & ~skip
    show = list(dict.fromkeys([str(df.columns[0]), *map(str, used)]))
    ex = df.loc[bad, show].head(SAMPLE).to_dict("records")
    n = int(bad.sum())
    return CheckResult(
        "rule",
        name,
        severity,
        n == 0,
        n,
        f"'{expr}' holds on every row" if n == 0 else f"'{expr}' is false on {n:,} row{'s' if n != 1 else ''}",
        ex,
    )


# ---------------------------------------------------------------- helpers
def as_text(s: pd.Series) -> pd.Series:
    """Values as plain Python strings ("" for blanks), whatever pandas' string backend is."""
    return pd.Series([("" if _blank(v) else str(v)) for v in s], index=s.index, dtype=object)


def is_present(s: pd.Series) -> pd.Series:
    """True where a value is filled in: not null and not just whitespace."""
    return pd.Series([not _blank(v) and str(v).strip() != "" for v in s], index=s.index, dtype=bool)


def _blank(v: Any) -> bool:
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def coerce(s: pd.Series, typ: str) -> tuple[pd.Series, pd.Series]:
    """(values converted to the contract type, mask of values that could not be converted)."""
    if typ == "string":
        return as_text(s), pd.Series(False, index=s.index)
    if typ in ("integer", "float"):
        num = pd.to_numeric(s, errors="coerce")
        bad = num.isna() & s.notna()
        if typ == "integer":
            bad |= num.notna() & (num % 1 != 0)
        return num, bad
    if typ == "boolean":
        m = {"true": True, "false": False, "1": True, "0": False, "yes": True, "no": False, "t": True, "f": False}
        conv = s.map(lambda v: v if isinstance(v, bool) else m.get(str(v).strip().lower()))
        return conv, conv.isna() & s.notna()
    if typ in ("date", "timestamp"):
        d = pd.to_datetime(s, errors="coerce", format="mixed", utc=True)
        bad = d.isna() & s.notna()
        if typ == "date":
            bad |= d.notna() & (d != d.dt.normalize())  # a time of day where a date was promised
        return d, bad
    raise ValueError(f"unknown type {typ}")


def _bound(v: Any, typ: str) -> Any:
    if v is None:
        return None
    if typ in ("date", "timestamp"):
        return pd.Timestamp(v, tz="UTC") if pd.Timestamp(v).tzinfo is None else pd.Timestamp(v).tz_convert("UTC")
    return float(v)


def _result(check: str, target: str, sev: str, bad: pd.Series, values: Any, ok_msg: str, bad_msg: str) -> CheckResult:
    bad = bad.fillna(False).astype(bool)
    n = int(bad.sum())
    src = values if isinstance(values, pd.Series) else pd.Series(values, index=bad.index)
    ex = [None if pd.isna(v) else (v.item() if hasattr(v, "item") else v) for v in src[bad].head(SAMPLE).tolist()]
    return CheckResult(
        check,
        target,
        sev,
        n == 0,
        n,
        ok_msg if n == 0 else f"{n:,} {bad_msg if n != 1 else bad_msg.replace('values', 'value')}",
        ex,
    )


def _range_text(lo: Any, hi: Any) -> str:
    if lo is not None and hi is not None:
        return f"{lo}..{hi}"
    if lo is not None:
        return f">= {lo}"
    return f"<= {hi}"
