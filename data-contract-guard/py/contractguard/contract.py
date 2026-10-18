"""The data contract: what a dataset promises its consumers, loaded from YAML and checked for mistakes.

A contract is plain YAML so that producers and consumers can review it in a pull request:

    dataset: orders
    version: 1.0.0
    owner: data-platform@example.com
    columns:
      - name: order_id
        type: string
        nullable: false
        unique: true
        pattern: "^ORD-[0-9]{6}$"
      - name: amount
        type: float
        min: 0
    rules:
      - name: ships_after_order
        expr: ship_date >= order_date
    dataset_checks:
      row_count: {min: 1}
      primary_key: [order_id]
      freshness: {column: order_date, max_age_days: 2}

Mistakes in the contract itself (unknown keys, a min above a max, an unknown type) raise ContractError with
every problem listed, so a broken contract never silently passes data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

TYPES = ("string", "integer", "float", "boolean", "date", "timestamp")
SEVERITIES = ("error", "warn")
COLUMN_KEYS = {
    "name",
    "type",
    "required",
    "nullable",
    "unique",
    "min",
    "max",
    "allowed",
    "pattern",
    "min_length",
    "max_length",
    "severity",
    "description",
}
TOP_KEYS = {"dataset", "version", "owner", "description", "columns", "rules", "dataset_checks"}
DATASET_KEYS = {"row_count", "primary_key", "freshness", "allow_extra_columns"}


class ContractError(ValueError):
    """The contract file is not valid. `problems` lists every issue found."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("invalid contract:\n  - " + "\n  - ".join(problems))


@dataclass(frozen=True)
class Column:
    name: str
    type: str = "string"
    required: bool = True  # the column must exist in the data
    nullable: bool = True
    unique: bool = False
    min: float | str | None = None
    max: float | str | None = None
    allowed: tuple[Any, ...] | None = None
    pattern: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    severity: str = "error"
    description: str | None = None


@dataclass(frozen=True)
class Rule:
    name: str
    expr: str
    severity: str = "error"
    description: str | None = None


@dataclass(frozen=True)
class Contract:
    dataset: str
    columns: tuple[Column, ...]
    version: str = "0.0.0"
    owner: str | None = None
    description: str | None = None
    rules: tuple[Rule, ...] = ()
    row_count_min: int | None = None
    row_count_max: int | None = None
    primary_key: tuple[str, ...] = ()
    freshness_column: str | None = None
    freshness_max_age_days: float | None = None
    allow_extra_columns: bool = True
    source: str | None = field(default=None, compare=False)

    def column(self, name: str) -> Column | None:
        return next((c for c in self.columns if c.name == name), None)


def load_contract(path: str | Path) -> Contract:
    p = Path(path)
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ContractError([f"{p}: not valid YAML ({error})"]) from error
    c = parse_contract(raw)
    return Contract(**{**c.__dict__, "source": str(p)})


def parse_contract(raw: Any) -> Contract:
    problems: list[str] = []
    if not isinstance(raw, dict):
        raise ContractError(["the contract must be a YAML mapping"])
    for k in sorted(set(raw) - TOP_KEYS):
        problems.append(f"unknown top-level key '{k}' (allowed: {', '.join(sorted(TOP_KEYS))})")
    dataset = raw.get("dataset")
    if not isinstance(dataset, str) or not dataset.strip():
        problems.append("'dataset' (the dataset's name) is required")
    version = str(raw.get("version", "0.0.0"))
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        problems.append(f"'version' must look like 1.2.3 (semantic versioning), got '{version}'")

    cols_raw = raw.get("columns")
    columns: list[Column] = []
    if not isinstance(cols_raw, list) or not cols_raw:
        problems.append("'columns' must be a non-empty list")
        cols_raw = []
    seen: set[str] = set()
    for i, c in enumerate(cols_raw):
        where = f"columns[{i}]"
        if not isinstance(c, dict):
            problems.append(f"{where}: must be a mapping")
            continue
        name = c.get("name")
        if not isinstance(name, str) or not name:
            problems.append(f"{where}: 'name' is required")
            continue
        where = f"column '{name}'"
        if name in seen:
            problems.append(f"{where}: defined twice")
        seen.add(name)
        for k in sorted(set(c) - COLUMN_KEYS):
            problems.append(f"{where}: unknown key '{k}'")
        typ = c.get("type", "string")
        if typ not in TYPES:
            problems.append(f"{where}: unknown type '{typ}' (allowed: {', '.join(TYPES)})")
        sev = c.get("severity", "error")
        if sev not in SEVERITIES:
            problems.append(f"{where}: severity must be 'error' or 'warn'")
        lo, hi = c.get("min"), c.get("max")
        if lo is not None and hi is not None:
            try:
                if _comparable(lo) > _comparable(hi):
                    problems.append(f"{where}: min ({lo}) is above max ({hi})")
            except TypeError:
                problems.append(f"{where}: min and max are not comparable")
        if (lo is not None or hi is not None) and typ in ("string", "boolean"):
            problems.append(f"{where}: min/max make no sense for type '{typ}' (use min_length/max_length)")
        pattern = c.get("pattern")
        if pattern is not None:
            try:
                re.compile(pattern)
            except re.error as error:
                problems.append(f"{where}: pattern is not a valid regular expression ({error})")
        allowed = c.get("allowed")
        if allowed is not None and not isinstance(allowed, list):
            problems.append(f"{where}: 'allowed' must be a list")
        for k in ("min_length", "max_length"):
            v = c.get(k)
            if v is not None and (not isinstance(v, int) or v < 0):
                problems.append(f"{where}: '{k}' must be a whole number >= 0")
        columns.append(
            Column(
                name=name,
                type=typ if typ in TYPES else "string",
                required=bool(c.get("required", True)),
                nullable=bool(c.get("nullable", True)),
                unique=bool(c.get("unique", False)),
                min=lo,
                max=hi,
                allowed=tuple(allowed) if isinstance(allowed, list) else None,
                pattern=pattern,
                min_length=c.get("min_length"),
                max_length=c.get("max_length"),
                severity=sev if sev in SEVERITIES else "error",
                description=c.get("description"),
            )
        )

    rules: list[Rule] = []
    for i, r in enumerate(raw.get("rules") or []):
        if not isinstance(r, dict) or not r.get("name") or not r.get("expr"):
            problems.append(f"rules[{i}]: needs 'name' and 'expr'")
            continue
        sev = r.get("severity", "error")
        if sev not in SEVERITIES:
            problems.append(f"rule '{r['name']}': severity must be 'error' or 'warn'")
        rules.append(
            Rule(
                name=str(r["name"]),
                expr=str(r["expr"]),
                severity=sev if sev in SEVERITIES else "error",
                description=r.get("description"),
            )
        )

    ds = raw.get("dataset_checks") or {}
    if not isinstance(ds, dict):
        problems.append("'dataset_checks' must be a mapping")
        ds = {}
    for k in sorted(set(ds) - DATASET_KEYS):
        problems.append(f"dataset_checks: unknown key '{k}'")
    rc = ds.get("row_count") or {}
    rmin, rmax = rc.get("min"), rc.get("max")
    if rmin is not None and rmax is not None and rmin > rmax:
        problems.append("dataset_checks.row_count: min is above max")
    pk = ds.get("primary_key") or []
    if isinstance(pk, str):
        pk = [pk]
    for k in pk:
        if k not in seen:
            problems.append(f"dataset_checks.primary_key: '{k}' is not a column in the contract")
    fr = ds.get("freshness") or {}
    if fr and (fr.get("column") not in seen or fr.get("max_age_days") is None):
        problems.append("dataset_checks.freshness: needs a contract 'column' and 'max_age_days'")

    if problems:
        raise ContractError(problems)
    return Contract(
        dataset=str(dataset),
        version=version,
        owner=raw.get("owner"),
        description=raw.get("description"),
        columns=tuple(columns),
        rules=tuple(rules),
        row_count_min=rmin,
        row_count_max=rmax,
        primary_key=tuple(pk),
        freshness_column=fr.get("column"),
        freshness_max_age_days=fr.get("max_age_days"),
        allow_extra_columns=bool(ds.get("allow_extra_columns", True)),
    )


def _comparable(v: Any) -> Any:
    return str(v) if hasattr(v, "isoformat") else v


def contract_to_dict(c: Contract) -> dict[str, Any]:
    """The contract as plain data, in the same shape as the YAML (for `infer` and round trips)."""
    cols = []
    for col in c.columns:
        d: dict[str, Any] = {"name": col.name, "type": col.type}
        defaults = Column(name=col.name)
        for k in (
            "required",
            "nullable",
            "unique",
            "min",
            "max",
            "pattern",
            "min_length",
            "max_length",
            "severity",
            "description",
        ):
            v = getattr(col, k)
            if v != getattr(defaults, k):
                d[k] = v
        if col.allowed is not None:
            d["allowed"] = list(col.allowed)
        cols.append(d)
    out: dict[str, Any] = {"dataset": c.dataset, "version": c.version}
    if c.owner:
        out["owner"] = c.owner
    if c.description:
        out["description"] = c.description
    out["columns"] = cols
    if c.rules:
        out["rules"] = [
            {
                "name": r.name,
                "expr": r.expr,
                **({"severity": r.severity} if r.severity != "error" else {}),
                **({"description": r.description} if r.description else {}),
            }
            for r in c.rules
        ]
    ds: dict[str, Any] = {}
    if c.row_count_min is not None or c.row_count_max is not None:
        ds["row_count"] = {k: v for k, v in (("min", c.row_count_min), ("max", c.row_count_max)) if v is not None}
    if c.primary_key:
        ds["primary_key"] = list(c.primary_key)
    if c.freshness_column:
        ds["freshness"] = {"column": c.freshness_column, "max_age_days": c.freshness_max_age_days}
    if not c.allow_extra_columns:
        ds["allow_extra_columns"] = False
    if ds:
        out["dataset_checks"] = ds
    return out
