"""Compare two versions of a contract and say which changes break consumers.

A change is BREAKING when data that satisfied the old contract's consumers can now arrive in a shape they
did not plan for, or when a column they rely on disappears: removing or renaming a column, changing a type,
making a column nullable, dropping uniqueness, widening a range or the allowed values, loosening a pattern.
A change is NON-BREAKING when it only adds promises or new optional columns.

The rule of thumb matches semantic versioning: a breaking change needs a major version bump, so `diff`
also checks that the new version number was bumped enough.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contract import Column, Contract

# A type change is breaking even when it widens (integer -> float): consumers that cast, join or aggregate on
# the old type break. Only these changes are safe because every old value reads the same under the new type.
SAFE_TYPE_CHANGES: set[tuple[str, str]] = set()


@dataclass(frozen=True)
class Change:
    kind: str  # "breaking" | "non-breaking"
    target: str
    message: str


@dataclass
class DiffReport:
    old_version: str
    new_version: str
    changes: list[Change]

    @property
    def breaking(self) -> list[Change]:
        return [c for c in self.changes if c.kind == "breaking"]

    @property
    def required_bump(self) -> str:
        if self.breaking:
            return "major"
        return "minor" if self.changes else "none"

    @property
    def version_ok(self) -> bool:
        o, n = _v(self.old_version), _v(self.new_version)
        need = self.required_bump
        if need == "major":
            return n[0] > o[0]
        if need == "minor":
            return n > o
        return n >= o


def diff_contracts(old: Contract, new: Contract) -> DiffReport:
    ch: list[Change] = []

    def b(t: str, m: str) -> None:
        ch.append(Change("breaking", t, m))

    def nb(t: str, m: str) -> None:
        ch.append(Change("non-breaking", t, m))

    old_cols = {c.name: c for c in old.columns}
    new_cols = {c.name: c for c in new.columns}
    for name in old_cols.keys() - new_cols.keys():
        b(name, "column removed")
    for name in sorted(new_cols.keys() - old_cols.keys()):
        c = new_cols[name]
        (b if c.required and not c.nullable else nb)(
            name,
            "new column added"
            + (" (required and not nullable: old producers will fail it)" if c.required and not c.nullable else ""),
        )
    for name in sorted(old_cols.keys() & new_cols.keys()):
        _column(old_cols[name], new_cols[name], b, nb)

    if old.primary_key != new.primary_key:
        b("dataset", f"primary key changed {list(old.primary_key)} -> {list(new.primary_key)}")
    if (new.row_count_min or 0) < (old.row_count_min or 0):
        b("dataset", f"minimum row count lowered {old.row_count_min} -> {new.row_count_min}")
    if (
        new.freshness_max_age_days
        and old.freshness_max_age_days
        and new.freshness_max_age_days > old.freshness_max_age_days
    ):
        b("dataset", f"freshness limit loosened {old.freshness_max_age_days} -> {new.freshness_max_age_days} days")
    if old.freshness_column and not new.freshness_column:
        b("dataset", "freshness check removed")
    if new.allow_extra_columns and not old.allow_extra_columns:
        nb("dataset", "extra columns now allowed")
    old_rules = {r.name: r for r in old.rules}
    new_rules = {r.name: r for r in new.rules}
    for n in sorted(old_rules.keys() - new_rules.keys()):
        b(n, "rule removed")
    for n in sorted(new_rules.keys() - old_rules.keys()):
        nb(n, "rule added")
    for n in sorted(old_rules.keys() & new_rules.keys()):
        if old_rules[n].expr != new_rules[n].expr:
            b(n, f"rule changed '{old_rules[n].expr}' -> '{new_rules[n].expr}'")
        if old_rules[n].severity == "error" and new_rules[n].severity == "warn":
            b(n, "rule downgraded from error to warn")
    return DiffReport(old.version, new.version, ch)


def _column(o: Column, n: Column, b, nb) -> None:  # type: ignore[no-untyped-def]
    t = o.name
    if o.type != n.type:
        (nb if (o.type, n.type) in SAFE_TYPE_CHANGES else b)(t, f"type changed {o.type} -> {n.type}")
    if not o.nullable and n.nullable:
        b(t, "now nullable")
    if o.nullable and not n.nullable:
        nb(t, "now not nullable")
    if o.required and not n.required:
        b(t, "no longer required")
    if o.unique and not n.unique:
        b(t, "no longer unique")
    if not o.unique and n.unique:
        nb(t, "now unique")
    for side, wider in (
        ("min", lambda a, c: c is None or (a is not None and c < a)),
        ("max", lambda a, c: c is None or (a is not None and c > a)),
    ):
        a, c = getattr(o, side), getattr(n, side)
        if a == c:
            continue
        if a is not None and wider(a, c):
            b(t, f"{side} loosened {a} -> {c}")
        else:
            nb(t, f"{side} tightened {a} -> {c}")
    if o.allowed is not None:
        added = set(map(str, n.allowed or ())) - set(map(str, o.allowed))
        if n.allowed is None:
            b(t, "allowed-values list removed")
        elif added:
            b(t, f"new allowed values {sorted(added)} (consumers may not handle them)")
        elif set(map(str, n.allowed)) != set(map(str, o.allowed)):
            nb(t, "allowed values narrowed")
    elif n.allowed is not None:
        nb(t, "allowed-values list added")
    if o.pattern != n.pattern:
        (b if o.pattern is not None else nb)(t, f"pattern changed {o.pattern!r} -> {n.pattern!r}")
    if o.max_length is not None and (n.max_length is None or n.max_length > o.max_length):
        b(t, f"max_length loosened {o.max_length} -> {n.max_length}")
    if o.severity == "error" and n.severity == "warn":
        b(t, "checks downgraded from error to warn")


def _v(s: str) -> tuple[int, int, int]:
    a, b, c = (int(x) for x in s.split("."))
    return a, b, c
