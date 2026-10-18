"""contract-guard: validate data against a contract, draft a contract from data, and diff contract versions.

Exit codes: 0 everything passed, 1 the data broke the contract (or a diff found an unbumped breaking change),
2 the contract or data file itself could not be used.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import __version__
from .checks import validate
from .contract import ContractError, contract_to_dict, load_contract
from .diff import diff_contracts
from .infer import infer_contract
from .io import DataError, read_data
from .report import diff_json, diff_text, render, to_markdown


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="contract-guard", description=__doc__.splitlines()[0])
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="check a data file against a contract")
    v.add_argument("data", nargs="+", help="data file(s): .csv .tsv .parquet .jsonl .json")
    v.add_argument("-c", "--contract", required=True, help="contract YAML")
    v.add_argument("-f", "--format", default="text", choices=["text", "json", "markdown", "junit"])
    v.add_argument("-o", "--output", help="write the report to a file instead of stdout")
    v.add_argument("--data-format", help="force the data file type")
    v.add_argument("--as-of", help="judge freshness as of this ISO time (default: $CONTRACT_GUARD_AS_OF or now)")
    v.add_argument("--warn-only", action="store_true", help="report but always exit 0 (for a soft rollout)")
    v.add_argument("-v", "--verbose", action="store_true", help="list passing checks too")

    i = sub.add_parser("infer", help="draft a contract from a sample data file")
    i.add_argument("data")
    i.add_argument("--dataset", help="dataset name (default: the file name)")
    i.add_argument("--owner")
    i.add_argument("-o", "--output", help="write the YAML to a file")

    d = sub.add_parser("diff", help="classify changes between two contract versions")
    d.add_argument("old")
    d.add_argument("new")
    d.add_argument("-f", "--format", default="text", choices=["text", "json", "markdown"])
    d.add_argument("--allow-breaking", action="store_true", help="exit 0 even if a breaking change is unbumped")

    sub.add_parser("check", help="only check that contract files are valid").add_argument("contracts", nargs="+")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return {"validate": _validate, "infer": _infer, "diff": _diff, "check": _check}[args.command](args)
    except (ContractError, DataError) as error:
        print(f"contract-guard: {error}", file=sys.stderr)
        return 2


def _validate(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    stamp = args.as_of or os.environ.get("CONTRACT_GUARD_AS_OF")
    as_of = datetime.fromisoformat(stamp) if stamp else datetime.now(timezone.utc)
    outputs, failed = [], False
    for path in args.data:
        report = validate(read_data(path, args.data_format), contract, as_of=as_of, source=path)
        failed |= not report.ok
        outputs.append(render(report, args.format, args.verbose))
        summary = os.environ.get("GITHUB_STEP_SUMMARY")  # inside GitHub Actions: show the table on the run page
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write(to_markdown(report) + "\n")
    text = "\n".join(outputs)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0 if (not failed or args.warn_only) else 1


def _infer(args: argparse.Namespace) -> int:
    df = read_data(args.data)
    c = infer_contract(df, dataset=args.dataset or Path(args.data).stem, owner=args.owner)
    text = (
        "# Drafted by contract-guard infer from "
        + Path(args.data).name
        + ". Review every bound before committing.\n"
        + yaml.safe_dump(contract_to_dict(c), sort_keys=False, allow_unicode=True)
    )
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"wrote {args.output} ({len(c.columns)} columns)")
    else:
        print(text, end="")
    return 0


def _diff(args: argparse.Namespace) -> int:
    d = diff_contracts(load_contract(args.old), load_contract(args.new))
    print(diff_json(d) if args.format == "json" else diff_text(d, markdown=args.format == "markdown"))
    return 0 if (d.version_ok or args.allow_breaking) else 1


def _check(args: argparse.Namespace) -> int:
    bad = 0
    for path in args.contracts:
        try:
            c = load_contract(path)
            print(f"ok   {path}  ({c.dataset} v{c.version}, {len(c.columns)} columns, {len(c.rules)} rules)")
        except ContractError as error:
            bad += 1
            print(f"bad  {path}\n" + "\n".join(f"     - {p}" for p in error.problems))
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
