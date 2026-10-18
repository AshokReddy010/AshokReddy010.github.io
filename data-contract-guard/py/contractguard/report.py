"""Turn a validation or diff report into text for people, JSON for machines, Markdown for pull requests, JUnit for CI."""

from __future__ import annotations

import json
from typing import Any
from xml.sax.saxutils import escape

from .checks import ValidationReport
from .diff import DiffReport

ICON = {"pass": "PASS", "fail": "FAIL", "warn": "WARN"}
MD_ICON = {"pass": "✅", "fail": "❌", "warn": "⚠️"}


def _ex(v: Any) -> str:
    s = json.dumps(v, default=str, ensure_ascii=False)
    return s if len(s) <= 120 else s[:117] + "..."


def to_dict(r: ValidationReport) -> dict[str, Any]:
    return {
        "dataset": r.dataset,
        "contract_version": r.contract_version,
        "source": r.source,
        "rows": r.rows,
        "ok": r.ok,
        "errors": len(r.errors),
        "warnings": len(r.warnings),
        "checks": [
            {
                "check": c.check,
                "target": c.target,
                "severity": c.severity,
                "status": c.status,
                "failing_rows": c.failing_rows,
                "message": c.message,
                "examples": json.loads(json.dumps(c.examples, default=str)),
            }
            for c in r.results
        ],
    }


def to_json(r: ValidationReport) -> str:
    return json.dumps(to_dict(r), indent=2, ensure_ascii=False)


def to_text(r: ValidationReport, verbose: bool = False) -> str:
    lines = [
        f"contract: {r.dataset} v{r.contract_version}" + (f"   data: {r.source}" if r.source else ""),
        f"rows: {r.rows:,}",
        "",
    ]
    for c in r.results:
        if c.status == "pass" and not verbose:
            continue
        lines.append(f"  {ICON[c.status]}  {c.target:<22} {c.check:<17} {c.message}")
        if c.examples and c.status != "pass":
            lines.append(f"        e.g. {', '.join(_ex(e) for e in c.examples[:3])}")
    passed = sum(1 for c in r.results if c.status == "pass")
    if not verbose and passed:
        lines.append(f"  {passed} checks passed")
    lines += [
        "",
        f"{'PASSED' if r.ok else 'FAILED'}: {len(r.errors)} errors, {len(r.warnings)} warnings, "
        f"{len(r.results)} checks",
    ]
    return "\n".join(lines)


def to_markdown(r: ValidationReport) -> str:
    head = "✅ passed" if r.ok else "❌ failed"
    out = [
        f"### Data contract `{r.dataset}` v{r.contract_version}: {head}",
        "",
        f"{r.rows:,} rows · {len(r.errors)} errors · {len(r.warnings)} warnings · {len(r.results)} checks",
        "",
    ]
    bad = [c for c in r.results if c.status != "pass"]
    if bad:
        out += ["| | Target | Check | Failing rows | Details | Examples |", "|---|---|---|---:|---|---|"]
        for c in bad:
            ex = ", ".join(f"`{_ex(e)}`".replace("|", "\\|") for e in c.examples[:3])
            out.append(
                f"| {MD_ICON[c.status]} | `{c.target}` | {c.check} | {c.failing_rows:,} | "
                f"{c.message.replace('|', chr(92) + '|')} | {ex} |"
            )
    else:
        out.append("Every check passed.")
    return "\n".join(out) + "\n"


def to_junit(r: ValidationReport) -> str:
    """One test case per check, so CI systems show contract failures next to unit-test failures."""
    cases = []
    for c in r.results:
        name = escape(f"{c.target}.{c.check}", {'"': "&quot;"})
        body = ""
        if c.status == "fail":
            body = f'<failure message="{escape(c.message, {chr(34): "&quot;"})}">{escape(_ex(c.examples))}</failure>'
        elif c.status == "warn":
            body = f"<system-out>{escape('WARN: ' + c.message)}</system-out>"
        cases.append(f'    <testcase classname="contract.{escape(r.dataset)}" name="{name}">{body}</testcase>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuites><testsuite name="data-contract:{escape(r.dataset)}" tests="{len(r.results)}" '
        f'failures="{len(r.errors)}" errors="0" skipped="0">\n' + "\n".join(cases) + "\n</testsuite></testsuites>\n"
    )


def render(r: ValidationReport, fmt: str, verbose: bool = False) -> str:
    if fmt == "json":
        return to_json(r)
    if fmt == "markdown":
        return to_markdown(r)
    if fmt == "junit":
        return to_junit(r)
    return to_text(r, verbose)


def diff_text(d: DiffReport, markdown: bool = False) -> str:
    if markdown:
        out = [f"### Contract change {d.old_version} → {d.new_version}", ""]
        if not d.changes:
            return "\n".join(out + ["No changes."]) + "\n"
        out += ["| | Target | Change |", "|---|---|---|"]
        out += [
            f"| {'💥 breaking' if c.kind == 'breaking' else '➕ safe'} | `{c.target}` | {c.message} |"
            for c in d.changes
        ]
        out += [
            "",
            f"Required version bump: **{d.required_bump}** — "
            f"{'version bumped correctly' if d.version_ok else 'the new version is not bumped enough'}",
        ]
        return "\n".join(out) + "\n"
    lines = [f"contract change {d.old_version} -> {d.new_version}"]
    for c in d.changes:
        lines.append(f"  {'BREAKING' if c.kind == 'breaking' else 'safe    '}  {c.target:<22} {c.message}")
    if not d.changes:
        lines.append("  no changes")
    lines.append(f"required bump: {d.required_bump}; {'version OK' if d.version_ok else 'VERSION NOT BUMPED ENOUGH'}")
    return "\n".join(lines)


def diff_json(d: DiffReport) -> str:
    return json.dumps(
        {
            "old_version": d.old_version,
            "new_version": d.new_version,
            "required_bump": d.required_bump,
            "version_ok": d.version_ok,
            "breaking": len(d.breaking),
            "changes": [c.__dict__ for c in d.changes],
        },
        indent=2,
    )
