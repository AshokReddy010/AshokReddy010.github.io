# Data Contract Guard

[![ci](https://github.com/AshokReddy010/data-contract-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/AshokReddy010/data-contract-guard/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10%20%7C%203.12%20%7C%203.13-blue)
![license](https://img.shields.io/badge/license-MIT-green)

**Data contracts as YAML, enforced in CI before bad data reaches anyone downstream.**

**▶ [Try it in your browser](https://ashokreddy010.github.io/data-contract-guard/)**: the real package runs client-side in Pyodide. Paste a contract and a CSV; nothing is uploaded.

A producer team writes down what its dataset promises (columns, types, keys, ranges, allowed values, business rules, freshness) in a YAML file that lives in the repo and is reviewed like code. `contract-guard` then does three jobs:

| Command | What it answers |
|---|---|
| `contract-guard validate` | Does this file keep every promise? If not, which rows break which promise, with examples. |
| `contract-guard infer` | What would a contract for this data look like? Drafts one from a sample to start from. |
| `contract-guard diff` | Will this contract change break consumers, and was the version bumped enough? |

![playground](docs/playground.png)

## Why

Most data incidents are not exotic: a column gets renamed, an enum gains a value nobody handles, an upstream bug ships negative quantities, a feed silently stops updating. These are cheap to catch at the boundary between teams and expensive to catch in a dashboard a week later. A contract makes the boundary explicit, and this tool turns it into a failing check.

## Quick start

```bash
pip install "git+https://github.com/AshokReddy010/data-contract-guard#egg=data-contract-guard[parquet]"

contract-guard validate -c examples/contracts/orders.yml examples/data/orders_broken.csv --as-of 2026-10-18
```

```
contract: orders v1.2.0   data: examples/data/orders_broken.csv
rows: 500

  FAIL  dataset                primary_key       2 rows share a key, 0 have a blank key part
        e.g. "ORD-100002", "ORD-100002"
  FAIL  order_id               pattern           1 value not matching ^ORD-[0-9]{6}$
        e.g. "ORD-12A"
  FAIL  customer_id            not_null          1 blank value
        e.g. "row 22"
  FAIL  quantity               type              1 value not of type integer
        e.g. "two"
  FAIL  status                 allowed_values    1 value not in the allowed list
        e.g. "lost_in_space"
  WARN  email                  pattern           1 value not matching ^[^@\s]+@[^@\s]+\.[a-z]{2,}$
  FAIL  ships_on_or_after_order rule             'ship_date >= order_date' is false on 1 row
        e.g. {"order_id": "ORD-100050", "order_date": "2026-09-07", "ship_date": "2026-08-01"}
  ...
FAILED: 10 errors, 1 warnings, 33 checks
```

Exit codes are built for CI: `0` passed, `1` the data broke the contract, `2` the contract or data file could not be used.

## The contract

```yaml
dataset: orders
version: 1.2.0                       # semantic versioning; `diff` enforces the bump
owner: data-platform@example.com
columns:
  - name: order_id
    type: string                     # string | integer | float | boolean | date | timestamp
    nullable: false
    unique: true
    pattern: "^ORD-[0-9]{6}$"
  - name: status
    type: string
    allowed: [placed, shipped, delivered, returned, cancelled]
  - name: discount
    type: float
    min: 0
    max: 0.5
  - name: email
    pattern: "^[^@\\s]+@[^@\\s]+\\.[a-z]{2,}$"
    severity: warn                   # reported, but does not fail the run
rules:
  - name: ships_on_or_after_order
    expr: ship_date >= order_date    # row-level rule; blanks are skipped
dataset_checks:
  row_count: {min: 100, max: 100000}
  primary_key: [order_id]            # composite keys allowed
  freshness: {column: order_date, max_age_days: 3}
  allow_extra_columns: false
```

Column keys: `type`, `required`, `nullable`, `unique`, `min`, `max` (numbers or dates), `allowed`, `pattern`, `min_length`, `max_length`, `severity`, `description`. The full example is [`examples/contracts/orders.yml`](examples/contracts/orders.yml).

**A broken contract never passes data.** Unknown keys, a `min` above a `max`, a bad regular expression, a primary key that is not a column: all of them are collected and reported together before any data is read (`contract-guard check contracts/*.yml` does only this).

## Design decisions

- **CSV is read as text.** If pandas inferred types, `"12a"` in an integer column would silently become a string column and the type check would have nothing to catch. Every value is checked as written.
- **Blank means missing.** Whitespace-only strings count as null, because that is how they behave downstream.
- **Each problem is reported once.** A missing column is one `required_columns` failure, not ten column failures; rules skip rows whose inputs are blank or unreadable, since the column checks already report those.
- **Failures carry examples.** Up to five offending values or rows per check, so the report is actionable without opening the file.
- **Breaking is defined from the consumer's side.** In `diff`, removing a column, changing a type (even integer → float), making a column nullable, dropping uniqueness, widening a range, adding an allowed value, loosening a pattern or freshness limit, or downgrading a check from error to warn are all breaking and need a major version. Adding optional columns or tightening a promise is safe and needs a minor version.

![diff](docs/diff.png)

## In GitHub Actions

The repo is also a composite action. It writes a Markdown report to the job summary, can emit JUnit XML for test-report actions, and can diff the contract against the base branch:

```yaml
- uses: actions/checkout@v4
  with: {fetch-depth: 0}
- uses: actions/setup-python@v5
  with: {python-version: "3.12"}
- uses: AshokReddy010/data-contract-guard@main
  with:
    contract: contracts/orders.yml
    data: exports/orders.csv
    junit-file: contract-report.xml
    diff-against: origin/${{ github.base_ref }}   # fail on an unbumped breaking change
    warn-only: "false"                             # "true" for a soft rollout
```

This repo's own CI dogfoods the action: the clean example must pass and the broken one must fail.

## As a library

```python
from contractguard import load_contract, validate
from contractguard.io import read_data

report = validate(read_data("orders.parquet"), load_contract("orders.yml"))
if not report.ok:
    for check in report.errors:
        print(check.target, check.check, check.message, check.examples)
```

Reports render as text, JSON, Markdown or JUnit (`contract-guard validate -f json|markdown|junit`).

## Project layout

```
src/contractguard/
  contract.py   YAML -> Contract, with every contract mistake collected
  checks.py     dataset, column and rule checks -> ValidationReport
  infer.py      draft a contract from a sample
  diff.py       breaking vs non-breaking changes, required version bump
  report.py     text / JSON / Markdown / JUnit
  io.py         CSV, TSV, Parquet, JSON Lines, JSON
  cli.py        the contract-guard command
action.yml      the GitHub Action
playground/     the in-browser demo (Pyodide) and its build script
examples/       orders contract, v1.3.0 proposal, clean and broken data (make_data.py regenerates them)
tests/          75 tests, 95% line coverage
```

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy src && pytest --cov=contractguard
python playground/build.py   # writes playground/site/ for the live demo
```

CI runs lint, format, type checks and tests on Python 3.10, 3.12 and 3.13, builds the wheel, and runs the action against the examples.

## Scope and limits

This is a single-node tool built on pandas: it is meant for files and extracts up to a few million rows, checked at the boundary between teams or in a pipeline step. It does not connect to warehouses directly; for very large tables, validate a sample or an export, or run the checks in the warehouse with dbt tests. The example data is synthetic and generated by `examples/make_data.py`.

## License

MIT
